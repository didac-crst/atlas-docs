"""Home screen task summaries (authz-aware, no inaccessible totals)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from atlasdocs.db.models import (
    EXTERNAL_SYSTEM_PAPERLESS,
    Entity,
    EntityType,
    IngestionJob,
    IngestionJobState,
    Relationship,
    RelationshipStatus,
)
from atlasdocs.security.tokens import token_fingerprint
from atlasdocs.services.documents import (
    DocumentService,
    ForbiddenDocumentError,
    NotFoundError,
    UnauthorizedError,
    UpstreamError,
)
from atlasdocs.services.paperless import (
    PaperlessAuthError,
    PaperlessClient,
    PaperlessDocument,
    PaperlessError,
    PaperlessUnavailableError,
)


@dataclass(frozen=True)
class CountStat:
    count: int
    capped: bool = False
    unavailable: bool = False


@dataclass(frozen=True)
class RecentDocumentItem:
    label: str
    entity_id: str | None
    href: str
    created_date: str | None = None


@dataclass(frozen=True)
class RecentKnowledgeItem:
    label: str
    relationship_type: str
    href: str


@dataclass(frozen=True)
class HomeSummary:
    needs_classification: CountStat
    needs_review: CountStat
    failed_ingestion: CountStat
    reconciliation_issues: CountStat
    recent_documents: list[RecentDocumentItem]
    recent_knowledge: list[RecentKnowledgeItem]


class HomeService:
    def __init__(self, session: Session, paperless: PaperlessClient) -> None:
        self._session = session
        self._paperless = paperless
        self._documents = DocumentService(session, paperless)
        self._access_cache: dict[int, PaperlessDocument | None] = {}

    def summarize(self, authorization: str) -> HomeSummary:
        if not authorization:
            raise UnauthorizedError("Authorization required")
        fingerprint = token_fingerprint(authorization)

        needs = self._count_unclassified(authorization)
        failed = self._count_failed_jobs(fingerprint)
        review = self._count_suggested(authorization)
        reconcile = self._count_missing_refs(authorization)
        recent_docs = self._recent_ready_documents(authorization, fingerprint)
        recent_knowledge = self._recent_relationships(authorization)

        return HomeSummary(
            needs_classification=needs,
            needs_review=review,
            failed_ingestion=failed,
            reconciliation_issues=reconcile,
            recent_documents=recent_docs,
            recent_knowledge=recent_knowledge,
        )

    def _accessible_document(self, doc_id: int, authorization: str) -> PaperlessDocument | None:
        if doc_id in self._access_cache:
            return self._access_cache[doc_id]
        try:
            doc = self._documents._ensure_paperless_access(doc_id, authorization)  # noqa: SLF001
        except (ForbiddenDocumentError, NotFoundError):
            self._access_cache[doc_id] = None
            return None
        except (UpstreamError, PaperlessUnavailableError, PaperlessError):
            raise
        self._access_cache[doc_id] = doc
        return doc

    def _count_unclassified(self, authorization: str) -> CountStat:
        try:
            page = self._documents.list_documents(
                authorization, page=1, page_size=25, classification="unclassified"
            )
        except UnauthorizedError:
            return CountStat(count=0, capped=False)
        except (PaperlessAuthError, ForbiddenDocumentError):
            return CountStat(count=0, capped=False)
        except (UpstreamError, PaperlessUnavailableError, PaperlessError):
            return CountStat(count=0, capped=False, unavailable=True)
        count = len(page.items)
        capped = page.has_next
        return CountStat(count=count, capped=capped)

    def _count_failed_jobs(self, fingerprint: str) -> CountStat:
        count = self._session.scalar(
            select(func.count())
            .select_from(IngestionJob)
            .where(
                IngestionJob.token_fingerprint == fingerprint,
                IngestionJob.state == IngestionJobState.failed,
            )
        )
        return CountStat(count=int(count or 0))

    def _count_suggested(self, authorization: str) -> CountStat:
        """Count suggested relationships whose document source is accessible."""
        # Bound the scan tightly: home only needs a small badge, not a full audit.
        rows = list(
            self._session.scalars(
                select(Relationship)
                .options(
                    joinedload(Relationship.source_entity).joinedload(Entity.external_reference),
                )
                .where(Relationship.status == RelationshipStatus.suggested)
                .order_by(Relationship.created_at.desc())
                .limit(25)
            ).unique()
        )
        accessible = 0
        try:
            for rel in rows:
                ref = rel.source_entity.external_reference if rel.source_entity else None
                if ref is None or ref.system != EXTERNAL_SYSTEM_PAPERLESS:
                    continue
                try:
                    doc_id = int(ref.external_id)
                except ValueError:
                    continue
                if self._accessible_document(doc_id, authorization) is not None:
                    accessible += 1
        except (UpstreamError, PaperlessUnavailableError, PaperlessError):
            return CountStat(count=0, capped=False, unavailable=True)
        return CountStat(count=accessible, capped=len(rows) >= 25)

    def _count_missing_refs(self, authorization: str) -> CountStat:
        """Bounded: Paperless docs without AtlasDocs external references."""
        try:
            batch = self._paperless.list_documents(authorization, page=1, page_size=25)
        except PaperlessAuthError:
            return CountStat(count=0)
        except PaperlessError:
            return CountStat(count=0, unavailable=True)
        missing = 0
        for doc in batch.results:
            if self._documents.get_external_reference(doc.id) is None:
                missing += 1
        return CountStat(count=missing, capped=batch.has_next)

    def _recent_ready_documents(
        self, authorization: str, fingerprint: str
    ) -> list[RecentDocumentItem]:
        jobs = list(
            self._session.scalars(
                select(IngestionJob)
                .where(
                    IngestionJob.token_fingerprint == fingerprint,
                    IngestionJob.state == IngestionJobState.ready,
                    IngestionJob.paperless_document_id.is_not(None),
                )
                .order_by(IngestionJob.updated_at.desc())
                .limit(8)
            )
        )
        items: list[RecentDocumentItem] = []
        for job in jobs:
            assert job.paperless_document_id is not None
            doc = self._accessible_document(job.paperless_document_id, authorization)
            if doc is None:
                continue
            entity = None
            if job.entity_id:
                entity = str(job.entity_id)
            items.append(
                RecentDocumentItem(
                    label=doc.title or job.original_filename,
                    entity_id=entity,
                    href=f"/documents/{job.paperless_document_id}",
                    created_date=doc.created_date,
                )
            )
        return items

    def _recent_relationships(self, authorization: str) -> list[RecentKnowledgeItem]:
        rows = list(
            self._session.scalars(
                select(Relationship)
                .options(
                    joinedload(Relationship.source_entity).joinedload(Entity.external_reference),
                    joinedload(Relationship.target_entity).joinedload(Entity.concept),
                    joinedload(Relationship.relationship_type),
                )
                .where(Relationship.status == RelationshipStatus.confirmed)
                .order_by(Relationship.created_at.desc())
                .limit(20)
            ).unique()
        )
        items: list[RecentKnowledgeItem] = []
        for rel in rows:
            ref = rel.source_entity.external_reference if rel.source_entity else None
            if ref is None or ref.system != EXTERNAL_SYSTEM_PAPERLESS:
                continue
            try:
                doc_id = int(ref.external_id)
            except ValueError:
                continue
            if self._accessible_document(doc_id, authorization) is None:
                continue
            target_label = "entity"
            if rel.target_entity and rel.target_entity.concept:
                target_label = rel.target_entity.concept.name
            elif rel.target_entity and rel.target_entity.entity_type == EntityType.document:
                target_label = "document"
            items.append(
                RecentKnowledgeItem(
                    label=target_label,
                    relationship_type=rel.relationship_type.code,
                    href=f"/documents/{doc_id}",
                )
            )
            if len(items) >= 8:
                break
        return items
