from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from atlasdocs.config import UNCLASSIFIED_MAX_UPSTREAM_PAGES, UNCLASSIFIED_PAGE_SIZE, get_settings
from atlasdocs.db.models import (
    Concept,
    DocumentReference,
    Entity,
    Ontology,
    Relationship,
    RelationshipOrigin,
    RelationshipStatus,
    RelationshipType,
)
from atlasdocs.services.paperless import (
    PaperlessAuthError,
    PaperlessClient,
    PaperlessDocument,
    PaperlessError,
    PaperlessNotFoundError,
    PaperlessUnavailableError,
)


class DomainError(Exception):
    """Semantic domain validation error."""


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class UpstreamError(DomainError):
    pass


class ForbiddenDocumentError(DomainError):
    """Document exists for someone else; must not be disclosed."""


class UnauthorizedError(DomainError):
    """Caller did not supply Paperless credentials."""


@dataclass(frozen=True)
class RelationshipView:
    id: str
    type: str
    target: str
    origin: str
    status: str


@dataclass(frozen=True)
class DocumentSemantics:
    paperless_document_id: int
    entity_id: str
    title: str | None
    open_url: str
    relationships: list[RelationshipView]


@dataclass(frozen=True)
class UnclassifiedDocument:
    paperless_document_id: int
    title: str | None


@dataclass(frozen=True)
class UnclassifiedPage:
    items: list[UnclassifiedDocument]
    page: int
    page_size: int
    paperless_count: int
    has_next: bool
    has_previous: bool
    next_page: int | None = None


@dataclass(frozen=True)
class RelationshipTypeView:
    code: str
    name: str
    target_ontology: str | None


@dataclass(frozen=True)
class ConceptView:
    code: str
    name: str


class DocumentService:
    def __init__(self, session: Session, paperless: PaperlessClient) -> None:
        self._session = session
        self._paperless = paperless
        self._settings = get_settings()

    def _require_token(self, token: str | None) -> str:
        if not token:
            raise UnauthorizedError("Authorization header required")
        return token

    def _ensure_paperless_access(self, paperless_document_id: int, token: str) -> PaperlessDocument:
        try:
            return self._paperless.assert_accessible(paperless_document_id, token=token)
        except PaperlessAuthError as exc:
            raise ForbiddenDocumentError(str(exc)) from exc
        except PaperlessNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        except PaperlessUnavailableError as exc:
            raise UpstreamError(str(exc)) from exc
        except PaperlessError as exc:
            raise UpstreamError(str(exc)) from exc

    def _get_or_create_document_reference(self, paperless_document_id: int) -> DocumentReference:
        existing = self._session.scalar(
            select(DocumentReference).where(
                DocumentReference.paperless_document_id == paperless_document_id
            )
        )
        if existing is not None:
            return existing

        entity = Entity()
        self._session.add(entity)
        self._session.flush()
        reference = DocumentReference(
            entity_id=entity.id,
            paperless_document_id=paperless_document_id,
        )
        self._session.add(reference)
        self._session.flush()
        return reference

    def _resolve_target_concept(
        self, relationship_type: RelationshipType, target: str
    ) -> Concept:
        def _matches(column) -> list[Concept]:
            stmt = select(Concept).where(column == target)
            if relationship_type.target_ontology_id is not None:
                stmt = stmt.where(Concept.ontology_id == relationship_type.target_ontology_id)
            return list(self._session.scalars(stmt))

        by_code = _matches(Concept.code)
        if len(by_code) == 1:
            return by_code[0]
        if len(by_code) > 1:
            raise ValidationError(f"Ambiguous target concept '{target}'")

        # Accept display names for API compatibility with the v0.1 curl examples.
        by_name = _matches(Concept.name)
        if len(by_name) == 1:
            return by_name[0]
        if len(by_name) > 1:
            raise ValidationError(f"Ambiguous target concept '{target}'")
        raise ValidationError(f"Unknown target concept '{target}'")

    def _relationship_views(self, reference: DocumentReference | None) -> list[RelationshipView]:
        if reference is None:
            return []
        views = [
            RelationshipView(
                id=str(rel.id),
                type=rel.relationship_type.code,
                target=rel.target_concept.name,
                origin=rel.origin.value,
                status=rel.status.value,
            )
            for rel in reference.entity.relationships
        ]
        views.sort(key=lambda item: (item.type, item.target))
        return views

    def _confirmed_paperless_ids(self, paperless_ids: list[int]) -> set[int]:
        if not paperless_ids:
            return set()
        rows = self._session.execute(
            select(DocumentReference.paperless_document_id)
            .join(Entity, Entity.id == DocumentReference.entity_id)
            .join(Relationship, Relationship.source_entity_id == Entity.id)
            .where(
                DocumentReference.paperless_document_id.in_(paperless_ids),
                Relationship.status == RelationshipStatus.confirmed,
            )
            .distinct()
        )
        return {int(row[0]) for row in rows}

    def get_document(self, paperless_document_id: int, token: str | None = None) -> DocumentSemantics:
        auth = self._require_token(token)
        paperless_doc = self._ensure_paperless_access(paperless_document_id, auth)
        reference = self._session.scalars(
            select(DocumentReference)
            .options(
                joinedload(DocumentReference.entity).joinedload(Entity.relationships).joinedload(
                    Relationship.relationship_type
                ),
                joinedload(DocumentReference.entity)
                .joinedload(Entity.relationships)
                .joinedload(Relationship.target_concept),
            )
            .where(DocumentReference.paperless_document_id == paperless_document_id)
        ).unique().one_or_none()
        return DocumentSemantics(
            paperless_document_id=paperless_document_id,
            entity_id=str(reference.entity_id) if reference else "",
            title=paperless_doc.title,
            open_url=self._settings.paperless_document_url(paperless_document_id),
            relationships=self._relationship_views(reference),
        )

    def list_unclassified(
        self,
        token: str | None = None,
        *,
        page: int = 1,
        page_size: int | None = None,
    ) -> UnclassifiedPage:
        auth = self._require_token(token)
        if page < 1:
            raise ValidationError("page must be >= 1")
        size = page_size or self._settings.unclassified_page_size or UNCLASSIFIED_PAGE_SIZE
        if size < 1 or size > UNCLASSIFIED_PAGE_SIZE:
            raise ValidationError(f"page_size must be between 1 and {UNCLASSIFIED_PAGE_SIZE}")
        max_upstream = (
            self._settings.unclassified_max_upstream_pages or UNCLASSIFIED_MAX_UPSTREAM_PAGES
        )

        items: list[UnclassifiedDocument] = []
        paperless_count = 0
        upstream_page = page
        pages_fetched = 0
        has_next = False
        last_page_fetched = page

        try:
            while len(items) < size and pages_fetched < max_upstream:
                paperless_page = self._paperless.list_documents(
                    auth, page=upstream_page, page_size=size
                )
                pages_fetched += 1
                last_page_fetched = upstream_page
                paperless_count = paperless_page.count
                ids = [doc.id for doc in paperless_page.results]
                confirmed = self._confirmed_paperless_ids(ids)
                for doc in paperless_page.results:
                    if doc.id in confirmed:
                        continue
                    items.append(
                        UnclassifiedDocument(
                            paperless_document_id=doc.id,
                            title=doc.title,
                        )
                    )
                    if len(items) >= size:
                        break

                if len(items) >= size:
                    # More upstream content may still exist on this or later pages.
                    has_next = paperless_page.has_next or len(paperless_page.results) == size
                    break

                if not paperless_page.has_next:
                    has_next = False
                    break

                upstream_page += 1
                has_next = True
        except PaperlessAuthError as exc:
            raise ForbiddenDocumentError(str(exc)) from exc
        except PaperlessNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        except PaperlessUnavailableError as exc:
            raise UpstreamError(str(exc)) from exc
        except PaperlessError as exc:
            raise UpstreamError(str(exc)) from exc

        return UnclassifiedPage(
            items=items[:size],
            page=page,
            page_size=size,
            paperless_count=paperless_count,
            has_next=has_next,
            has_previous=page > 1,
            next_page=(last_page_fetched + 1) if has_next else None,
        )

    def add_relationship(
        self,
        paperless_document_id: int,
        relationship_code: str,
        target: str,
        token: str | None = None,
        *,
        origin: RelationshipOrigin = RelationshipOrigin.manual,
        status: RelationshipStatus = RelationshipStatus.confirmed,
    ) -> DocumentSemantics:
        auth = self._require_token(token)
        self._ensure_paperless_access(paperless_document_id, auth)

        relationship_type = self._session.scalar(
            select(RelationshipType).where(RelationshipType.code == relationship_code)
        )
        if relationship_type is None:
            raise ValidationError(f"Unknown relationship type '{relationship_code}'")

        concept = self._resolve_target_concept(relationship_type, target)
        reference = self._get_or_create_document_reference(paperless_document_id)

        duplicate = self._session.scalar(
            select(Relationship).where(
                Relationship.source_entity_id == reference.entity_id,
                Relationship.relationship_type_id == relationship_type.id,
                Relationship.target_concept_id == concept.id,
            )
        )
        if duplicate is not None:
            raise ConflictError(
                "Relationship already exists for this document, type, and target"
            )

        relationship = Relationship(
            source_entity_id=reference.entity_id,
            relationship_type_id=relationship_type.id,
            target_concept_id=concept.id,
            origin=origin,
            status=status,
        )
        self._session.add(relationship)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "Relationship already exists for this document, type, and target"
            ) from exc

        return self.get_document(paperless_document_id, token=auth)

    def delete_relationship(self, relationship_id: str, token: str | None = None) -> None:
        auth = self._require_token(token)
        try:
            rel_uuid = uuid.UUID(relationship_id)
        except ValueError as exc:
            raise ValidationError("Invalid relationship id") from exc

        relationship = self._session.scalars(
            select(Relationship)
            .options(
                joinedload(Relationship.source_entity).joinedload(Entity.document_reference),
            )
            .where(Relationship.id == rel_uuid)
        ).unique().one_or_none()
        if relationship is None or relationship.source_entity.document_reference is None:
            raise NotFoundError("Relationship not found")

        paperless_id = relationship.source_entity.document_reference.paperless_document_id
        self._ensure_paperless_access(paperless_id, auth)
        self._session.delete(relationship)
        self._session.flush()

    def list_relationship_types(self) -> list[RelationshipTypeView]:
        rows = self._session.scalars(
            select(RelationshipType).options(joinedload(RelationshipType.target_ontology))
        ).unique()
        views = [
            RelationshipTypeView(
                code=item.code,
                name=item.name,
                target_ontology=item.target_ontology.code if item.target_ontology else None,
            )
            for item in rows
        ]
        views.sort(key=lambda item: item.code)
        return views

    def list_ontology_codes(self) -> list[str]:
        codes = list(self._session.scalars(select(Ontology.code)))
        codes.sort()
        return codes

    def list_concepts(self, ontology_code: str) -> list[ConceptView]:
        ontology = self._session.scalar(select(Ontology).where(Ontology.code == ontology_code))
        if ontology is None:
            raise NotFoundError(f"Ontology '{ontology_code}' not found")
        concepts = list(
            self._session.scalars(select(Concept).where(Concept.ontology_id == ontology.id))
        )
        concepts.sort(key=lambda item: item.name)
        return [ConceptView(code=item.code, name=item.name) for item in concepts]
