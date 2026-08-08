from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from atlasdocs.config import UNCLASSIFIED_MAX_UPSTREAM_PAGES, UNCLASSIFIED_PAGE_SIZE, get_settings
from atlasdocs.db.models import (
    EXTERNAL_SYSTEM_PAPERLESS,
    Concept,
    Entity,
    EntityType,
    ExternalReference,
    Ontology,
    Relationship,
    RelationshipDirectionality,
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
    target_entity_id: str
    origin: str
    status: str
    source_entity_id: str


@dataclass(frozen=True)
class EntityView:
    id: str
    entity_type: str
    label: str
    paperless_document_id: int | None
    title: str | None = None
    created_date: str | None = None
    correspondent: str | None = None
    document_type: str | None = None
    open_url: str | None = None
    relationships: list[RelationshipView] | None = None


@dataclass(frozen=True)
class DocumentSemantics:
    paperless_document_id: int
    entity_id: str
    title: str | None
    created_date: str | None
    correspondent: str | None
    document_type: str | None
    open_url: str | None
    relationships: list[RelationshipView]


@dataclass(frozen=True)
class UnclassifiedDocument:
    paperless_document_id: int
    title: str | None
    created_date: str | None = None
    correspondent: str | None = None
    document_type: str | None = None


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
    directionality: str
    inverse: str | None


@dataclass(frozen=True)
class ConceptView:
    code: str
    name: str


@dataclass(frozen=True)
class BulkRelationshipResult:
    paperless_document_id: int
    status: str
    relationship_id: str | None = None


@dataclass(frozen=True)
class EntitySearchHit:
    label: str
    entity_type: str
    id: str | None = None
    paperless_document_id: int | None = None
    subtitle: str | None = None
    open_url: str | None = None


class DocumentService:
    """Document facade and general entity relationship operations."""

    def __init__(self, session: Session, paperless: PaperlessClient) -> None:
        self._session = session
        self._paperless = paperless
        self._settings = get_settings()
        self._paperless_doc_cache: dict[tuple[str, int], PaperlessDocument] = {}
        self._validated_tokens: set[str] = set()

    def _require_token(self, token: str | None) -> str:
        if not token:
            raise UnauthorizedError("Authorization header required")
        return token

    def _validate_paperless_token(self, token: str) -> None:
        if token in self._validated_tokens:
            return
        try:
            self._paperless.validate_token(token)
        except PaperlessAuthError as exc:
            raise UnauthorizedError("Invalid Paperless credentials") from exc
        except PaperlessUnavailableError as exc:
            raise UpstreamError(str(exc)) from exc
        except PaperlessError as exc:
            raise UpstreamError(str(exc)) from exc
        self._validated_tokens.add(token)

    def _ensure_paperless_access(self, paperless_document_id: int, token: str) -> PaperlessDocument:
        cache_key = (token, paperless_document_id)
        cached = self._paperless_doc_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            document = self._paperless.assert_accessible(paperless_document_id, token=token)
        except PaperlessAuthError as exc:
            raise ForbiddenDocumentError(str(exc)) from exc
        except PaperlessNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        except PaperlessUnavailableError as exc:
            raise UpstreamError(str(exc)) from exc
        except PaperlessError as exc:
            raise UpstreamError(str(exc)) from exc
        self._paperless_doc_cache[cache_key] = document
        self._validated_tokens.add(token)
        return document

    def _paperless_external_id(self, paperless_document_id: int) -> str:
        return str(paperless_document_id)

    def _get_external_reference(self, paperless_document_id: int) -> ExternalReference | None:
        return self._session.scalar(
            select(ExternalReference).where(
                ExternalReference.system == EXTERNAL_SYSTEM_PAPERLESS,
                ExternalReference.external_id == self._paperless_external_id(paperless_document_id),
            )
        )

    def get_external_reference(self, paperless_document_id: int) -> ExternalReference | None:
        """Public helper for reconciliation flows."""
        return self._get_external_reference(paperless_document_id)

    def get_or_create_document_entity(self, paperless_document_id: int) -> Entity:
        """Public helper for reconciliation and document flows."""
        return self._get_or_create_document_entity(paperless_document_id)

    def _get_or_create_document_entity(self, paperless_document_id: int) -> Entity:
        existing = self._get_external_reference(paperless_document_id)
        if existing is not None:
            return existing.entity

        try:
            with self._session.begin_nested():
                entity = Entity(entity_type=EntityType.document)
                self._session.add(entity)
                self._session.flush()
                reference = ExternalReference(
                    entity_id=entity.id,
                    system=EXTERNAL_SYSTEM_PAPERLESS,
                    external_id=self._paperless_external_id(paperless_document_id),
                )
                self._session.add(reference)
                self._session.flush()
                return entity
        except IntegrityError:
            existing = self._get_external_reference(paperless_document_id)
            if existing is None:
                raise
            return existing.entity

    def _load_entity(self, entity_id: uuid.UUID) -> Entity:
        entity = self._session.scalars(
            select(Entity)
            .options(
                joinedload(Entity.external_reference),
                joinedload(Entity.concept).joinedload(Concept.ontology),
            )
            .where(Entity.id == entity_id)
        ).unique().one_or_none()
        if entity is None:
            raise NotFoundError("Entity not found")
        return entity

    def _paperless_id_for_entity(self, entity: Entity) -> int | None:
        ref = entity.external_reference
        if ref is None or ref.system != EXTERNAL_SYSTEM_PAPERLESS:
            return None
        try:
            return int(ref.external_id)
        except ValueError:
            return None

    def _ensure_entity_readable(self, entity: Entity, token: str) -> PaperlessDocument | None:
        reference = entity.external_reference
        if reference is None or reference.system != EXTERNAL_SYSTEM_PAPERLESS:
            # Concept/native entities are not Paperless-backed; still require a
            # Paperless-accepted token so callers cannot use arbitrary strings.
            self._validate_paperless_token(token)
            return None
        paperless_id = self._paperless_id_for_entity(entity)
        if paperless_id is None:
            raise ValidationError("Invalid Paperless external reference")
        return self._ensure_paperless_access(paperless_id, token)

    def _entity_label(self, entity: Entity) -> str:
        if entity.concept is not None:
            return entity.concept.name
        ref = entity.external_reference
        if ref is not None and ref.system == EXTERNAL_SYSTEM_PAPERLESS:
            return f"paperless:{ref.external_id}"
        if ref is not None:
            return f"{ref.system}:{ref.external_id}"
        return str(entity.id)

    def _target_label(self, relationship: Relationship) -> str:
        return self._entity_label(relationship.target_entity)

    def _relationship_view(self, relationship: Relationship) -> RelationshipView:
        return RelationshipView(
            id=str(relationship.id),
            type=relationship.relationship_type.code,
            target=self._target_label(relationship),
            target_entity_id=str(relationship.target_entity_id),
            origin=relationship.origin.value,
            status=relationship.status.value,
            source_entity_id=str(relationship.source_entity_id),
        )

    def _relationship_views(self, entity: Entity | None) -> list[RelationshipView]:
        if entity is None:
            return []
        views = [self._relationship_view(rel) for rel in entity.outgoing_relationships]
        views.sort(key=lambda item: (item.type, item.target))
        return views

    def _entity_relationship_options(self):
        return (
            joinedload(Entity.outgoing_relationships)
            .joinedload(Relationship.relationship_type)
            .joinedload(RelationshipType.inverse_relationship_type),
            joinedload(Entity.outgoing_relationships)
            .joinedload(Relationship.target_entity)
            .joinedload(Entity.concept),
            joinedload(Entity.outgoing_relationships)
            .joinedload(Relationship.target_entity)
            .joinedload(Entity.external_reference),
            joinedload(Entity.external_reference),
            joinedload(Entity.concept).joinedload(Concept.ontology),
        )

    def _confirmed_paperless_ids(self, paperless_ids: list[int]) -> set[int]:
        if not paperless_ids:
            return set()
        external_ids = [self._paperless_external_id(item) for item in paperless_ids]
        rows = self._session.execute(
            select(ExternalReference.external_id)
            .join(Entity, Entity.id == ExternalReference.entity_id)
            .join(Relationship, Relationship.source_entity_id == Entity.id)
            .where(
                ExternalReference.system == EXTERNAL_SYSTEM_PAPERLESS,
                ExternalReference.external_id.in_(external_ids),
                Relationship.status == RelationshipStatus.confirmed,
            )
            .distinct()
        )
        return {int(row[0]) for row in rows}

    def _find_edge(
        self,
        source_entity_id: uuid.UUID,
        relationship_type_id: uuid.UUID,
        target_entity_id: uuid.UUID,
    ) -> Relationship | None:
        return self._session.scalar(
            select(Relationship).where(
                Relationship.source_entity_id == source_entity_id,
                Relationship.relationship_type_id == relationship_type_id,
                Relationship.target_entity_id == target_entity_id,
            )
        )

    def _ensure_edge(
        self,
        *,
        source_entity_id: uuid.UUID,
        relationship_type_id: uuid.UUID,
        target_entity_id: uuid.UUID,
        origin: RelationshipOrigin,
        status: RelationshipStatus,
        created_by: str | None,
        model: str | None,
        prompt_version: str | None,
        generated_at: datetime | None,
        require_new: bool,
    ) -> Relationship:
        existing = self._find_edge(source_entity_id, relationship_type_id, target_entity_id)
        if existing is not None:
            if require_new:
                raise ConflictError(
                    "Relationship already exists for this source, type, and target"
                )
            return existing

        relationship = Relationship(
            source_entity_id=source_entity_id,
            relationship_type_id=relationship_type_id,
            target_entity_id=target_entity_id,
            origin=origin,
            status=status,
            created_by=created_by,
            model=model,
            prompt_version=prompt_version,
            generated_at=generated_at,
        )
        try:
            with self._session.begin_nested():
                self._session.add(relationship)
                self._session.flush()
                return relationship
        except IntegrityError as exc:
            if require_new:
                raise ConflictError(
                    "Relationship already exists for this source, type, and target"
                ) from exc
            existing = self._find_edge(source_entity_id, relationship_type_id, target_entity_id)
            if existing is None:
                raise
            return existing

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

        by_name = _matches(Concept.name)
        if len(by_name) == 1:
            return by_name[0]
        if len(by_name) > 1:
            raise ValidationError(f"Ambiguous target concept '{target}'")
        raise ValidationError(f"Unknown target concept '{target}'")

    def _resolve_target_entity(
        self,
        relationship_type: RelationshipType,
        *,
        target: str | None,
        target_entity_id: str | None,
        target_paperless_id: int | None,
        token: str,
    ) -> Entity:
        specified = [
            value is not None
            for value in (target, target_entity_id, target_paperless_id)
        ]
        if sum(specified) != 1:
            raise ValidationError(
                "Provide exactly one of target, target_entity_id, or target_paperless_id"
            )

        if target_entity_id is not None:
            try:
                entity_uuid = uuid.UUID(target_entity_id)
            except ValueError as exc:
                raise ValidationError("Invalid target_entity_id") from exc
            entity = self._load_entity(entity_uuid)
            self._ensure_entity_readable(entity, token)
            if (
                relationship_type.target_ontology_id is not None
                and (
                    entity.concept is None
                    or entity.concept.ontology_id != relationship_type.target_ontology_id
                )
            ):
                raise ValidationError("Target entity is outside the relationship type ontology")
            return entity

        if target_paperless_id is not None:
            if relationship_type.target_ontology_id is not None:
                raise ValidationError("This relationship type requires a concept target")
            self._ensure_paperless_access(target_paperless_id, token)
            return self._get_or_create_document_entity(target_paperless_id)

        assert target is not None
        concept = self._resolve_target_concept(relationship_type, target)
        return self._load_entity(concept.id)

    def _create_relationship_edges(
        self,
        *,
        source_entity: Entity,
        relationship_type: RelationshipType,
        target_entity: Entity,
        origin: RelationshipOrigin,
        status: RelationshipStatus,
        created_by: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        generated_at: datetime | None = None,
    ) -> None:
        if source_entity.id == target_entity.id:
            raise ValidationError("Source and target entities must differ")

        self._ensure_edge(
            source_entity_id=source_entity.id,
            relationship_type_id=relationship_type.id,
            target_entity_id=target_entity.id,
            origin=origin,
            status=status,
            created_by=created_by,
            model=model,
            prompt_version=prompt_version,
            generated_at=generated_at,
            require_new=True,
        )

        if relationship_type.directionality == RelationshipDirectionality.symmetric:
            self._ensure_edge(
                source_entity_id=target_entity.id,
                relationship_type_id=relationship_type.id,
                target_entity_id=source_entity.id,
                origin=origin,
                status=status,
                created_by=created_by,
                model=model,
                prompt_version=prompt_version,
                generated_at=generated_at,
                require_new=False,
            )

        inverse = relationship_type.inverse_relationship_type
        if inverse is not None:
            self._ensure_edge(
                source_entity_id=target_entity.id,
                relationship_type_id=inverse.id,
                target_entity_id=source_entity.id,
                origin=origin,
                status=status,
                created_by=created_by,
                model=model,
                prompt_version=prompt_version,
                generated_at=generated_at,
                require_new=False,
            )

    def get_entity(self, entity_id: str, token: str | None = None) -> EntityView:
        auth = self._require_token(token)
        try:
            entity_uuid = uuid.UUID(entity_id)
        except ValueError as exc:
            raise ValidationError("Invalid entity id") from exc

        entity = self._session.scalars(
            select(Entity)
            .options(*self._entity_relationship_options())
            .where(Entity.id == entity_uuid)
        ).unique().one_or_none()
        if entity is None:
            raise NotFoundError("Entity not found")

        paperless_doc = self._ensure_entity_readable(entity, auth)
        paperless_id = self._paperless_id_for_entity(entity)
        return EntityView(
            id=str(entity.id),
            entity_type=entity.entity_type.value,
            label=self._entity_label(entity),
            paperless_document_id=paperless_id,
            title=paperless_doc.title if paperless_doc else (
                entity.concept.name if entity.concept else None
            ),
            created_date=paperless_doc.created_date if paperless_doc else None,
            correspondent=paperless_doc.correspondent if paperless_doc else None,
            document_type=paperless_doc.document_type if paperless_doc else None,
            open_url=(
                self._settings.paperless_document_url(paperless_id)
                if paperless_id is not None
                else None
            ),
            relationships=self._relationship_views(entity),
        )

    def list_entity_relationships(
        self, entity_id: str, token: str | None = None
    ) -> list[RelationshipView]:
        return self.get_entity(entity_id, token=token).relationships or []

    def add_entity_relationship(
        self,
        entity_id: str,
        relationship_code: str,
        token: str | None = None,
        *,
        target: str | None = None,
        target_entity_id: str | None = None,
        target_paperless_id: int | None = None,
        origin: RelationshipOrigin = RelationshipOrigin.manual,
        status: RelationshipStatus = RelationshipStatus.confirmed,
        created_by: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        generated_at: datetime | None = None,
    ) -> EntityView:
        auth = self._require_token(token)
        try:
            entity_uuid = uuid.UUID(entity_id)
        except ValueError as exc:
            raise ValidationError("Invalid entity id") from exc

        source_entity = self._load_entity(entity_uuid)
        self._ensure_entity_readable(source_entity, auth)

        relationship_type = self._session.scalar(
            select(RelationshipType)
            .options(joinedload(RelationshipType.inverse_relationship_type))
            .where(RelationshipType.code == relationship_code)
        )
        if relationship_type is None:
            raise ValidationError(f"Unknown relationship type '{relationship_code}'")

        target_entity = self._resolve_target_entity(
            relationship_type,
            target=target,
            target_entity_id=target_entity_id,
            target_paperless_id=target_paperless_id,
            token=auth,
        )
        self._create_relationship_edges(
            source_entity=source_entity,
            relationship_type=relationship_type,
            target_entity=target_entity,
            origin=origin,
            status=status,
            created_by=created_by,
            model=model,
            prompt_version=prompt_version,
            generated_at=generated_at,
        )
        return self.get_entity(entity_id, token=auth)

    def get_document(self, paperless_document_id: int, token: str | None = None) -> DocumentSemantics:
        auth = self._require_token(token)
        paperless_doc = self._ensure_paperless_access(paperless_document_id, auth)
        reference = self._session.scalars(
            select(ExternalReference)
            .options(
                joinedload(ExternalReference.entity).options(*self._entity_relationship_options())
            )
            .where(
                ExternalReference.system == EXTERNAL_SYSTEM_PAPERLESS,
                ExternalReference.external_id
                == self._paperless_external_id(paperless_document_id),
            )
        ).unique().one_or_none()
        entity = reference.entity if reference else None
        return DocumentSemantics(
            paperless_document_id=paperless_document_id,
            entity_id=str(entity.id) if entity else "",
            title=paperless_doc.title,
            created_date=paperless_doc.created_date,
            correspondent=paperless_doc.correspondent,
            document_type=paperless_doc.document_type,
            open_url=self._settings.paperless_document_url(paperless_document_id),
            relationships=self._relationship_views(entity),
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
                            created_date=doc.created_date,
                            correspondent=doc.correspondent,
                            document_type=doc.document_type,
                        )
                    )
                    if len(items) >= size:
                        break

                if len(items) >= size:
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

    def list_documents(
        self,
        token: str | None = None,
        *,
        page: int = 1,
        page_size: int | None = None,
        q: str | None = None,
        classification: str = "unclassified",
        sort: str | None = None,
        order: str = "desc",
        created_gte: str | None = None,
        created_lte: str | None = None,
        correspondent: str | None = None,
        document_type: str | None = None,
        tag: str | None = None,
        completeness: str | None = None,
    ) -> UnclassifiedPage:
        """List documents with Paperless metadata filters + AtlasDocs classification."""
        auth = self._require_token(token)
        classification = (classification or "unclassified").strip().lower()
        if classification not in {"unclassified", "classified", "any"}:
            raise ValidationError("classification must be unclassified, classified, or any")
        completeness_norm = (completeness or "").strip().lower() or None
        if completeness_norm is not None and completeness_norm not in {
            "empty",
            "partial",
            "complete",
            "any",
        }:
            raise ValidationError("completeness must be empty, partial, complete, or any")
        if completeness_norm == "empty":
            classification = "unclassified"
        elif completeness_norm == "complete":
            classification = "classified"
        if page < 1:
            raise ValidationError("page must be >= 1")
        size = page_size or self._settings.unclassified_page_size or UNCLASSIFIED_PAGE_SIZE
        if size < 1 or size > UNCLASSIFIED_PAGE_SIZE:
            raise ValidationError(f"page_size must be between 1 and {UNCLASSIFIED_PAGE_SIZE}")
        order_norm = (order or "desc").strip().lower()
        if order_norm not in {"asc", "desc"}:
            raise ValidationError("order must be asc or desc")
        sort_norm = (sort or "created").strip().lower()
        if sort_norm not in {"created", "title", "id", "correspondent", "added"}:
            raise ValidationError("sort must be created, title, id, correspondent, or added")
        ordering_field = {
            "created": "created",
            "added": "added",
            "title": "title",
            "id": "id",
            "correspondent": "correspondent__name",
        }[sort_norm]
        ordering = f"-{ordering_field}" if order_norm == "desc" else ordering_field
        query = q.strip() if q else None
        created_gte = created_gte.strip() if created_gte else None
        created_lte = created_lte.strip() if created_lte else None
        correspondent = correspondent.strip() if correspondent else None
        document_type = document_type.strip() if document_type else None
        tag = tag.strip() if tag else None
        has_paperless_filters = any(
            [query, created_gte, created_lte, correspondent, document_type, tag]
        )

        if (
            classification == "unclassified"
            and not has_paperless_filters
            and order_norm == "desc"
            and sort_norm in {"created", "id"}
        ):
            # Preserve v0.4 fill-across-pages behavior for the unclassified queue.
            return self.list_unclassified(auth, page=page, page_size=size)

        max_upstream = (
            self._settings.unclassified_max_upstream_pages or UNCLASSIFIED_MAX_UPSTREAM_PAGES
        )
        items: list[UnclassifiedDocument] = []
        paperless_count = 0
        upstream_page = page
        pages_fetched = 0
        has_next = False
        last_page_fetched = page

        def _matches(doc_id: int, confirmed: set[int]) -> bool:
            if completeness_norm == "partial":
                # Suggested-only is rare; treat as classified-but-empty confirmed for now.
                return doc_id not in confirmed
            if classification == "any":
                return True
            if classification == "classified":
                return doc_id in confirmed
            return doc_id not in confirmed

        try:
            while len(items) < size and pages_fetched < max_upstream:
                paperless_page = self._paperless.list_documents(
                    auth,
                    page=upstream_page,
                    page_size=size,
                    query=query,
                    ordering=ordering,
                    created_gte=created_gte,
                    created_lte=created_lte,
                    correspondent=correspondent,
                    document_type=document_type,
                    tag=tag,
                )
                pages_fetched += 1
                last_page_fetched = upstream_page
                paperless_count = paperless_page.count
                ids = [doc.id for doc in paperless_page.results]
                confirmed = self._confirmed_paperless_ids(ids)
                for doc in paperless_page.results:
                    if not _matches(doc.id, confirmed):
                        continue
                    items.append(
                        UnclassifiedDocument(
                            paperless_document_id=doc.id,
                            title=doc.title,
                            created_date=doc.created_date,
                            correspondent=doc.correspondent,
                            document_type=doc.document_type,
                        )
                    )
                    if len(items) >= size:
                        break

                if classification == "any" and completeness_norm not in {"partial", "empty"}:
                    has_next = paperless_page.has_next
                    break

                if len(items) >= size:
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

    def search_entities(
        self,
        token: str | None = None,
        *,
        q: str = "",
        entity_type: str | None = None,
        ontology_code: str | None = None,
        limit: int = 25,
    ) -> list[EntitySearchHit]:
        """Search AtlasDocs entities for relationship targets (authz-filtered)."""
        auth = self._require_token(token)
        self._validate_paperless_token(auth)
        if limit < 1 or limit > 50:
            raise ValidationError("limit must be between 1 and 50")
        wanted = (entity_type or "any").strip().lower()
        if wanted not in {"any", "document", "concept"}:
            raise ValidationError("entity_type must be any, document, or concept")
        needle = q.strip()
        hits: list[EntitySearchHit] = []

        if wanted in {"any", "concept"}:
            query = select(Concept).options(
                joinedload(Concept.ontology), joinedload(Concept.entity)
            )
            if ontology_code:
                ontology = self._session.scalar(
                    select(Ontology).where(Ontology.code == ontology_code)
                )
                if ontology is None:
                    raise NotFoundError(f"Ontology '{ontology_code}' not found")
                query = query.where(Concept.ontology_id == ontology.id)
            if needle:
                escaped = (
                    needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                )
                pattern = f"%{escaped}%"
                query = query.where(
                    or_(
                        Concept.code.ilike(pattern, escape="\\"),
                        Concept.name.ilike(pattern, escape="\\"),
                    )
                )
            query = query.order_by(Concept.name).limit(limit)
            for row in self._session.scalars(query).unique():
                subtitle = row.ontology.code if row.ontology else None
                hits.append(
                    EntitySearchHit(
                        id=str(row.id),
                        label=row.name,
                        entity_type="concept",
                        subtitle=subtitle,
                    )
                )
                if len(hits) >= limit:
                    return hits[:limit]

        if wanted in {"any", "document"} and len(hits) < limit:
            remaining = limit - len(hits)
            try:
                page = self._paperless.list_documents(
                    auth,
                    page=1,
                    page_size=remaining,
                    query=needle or None,
                    ordering="-created",
                )
            except PaperlessAuthError as exc:
                raise ForbiddenDocumentError(str(exc)) from exc
            except PaperlessUnavailableError as exc:
                raise UpstreamError(str(exc)) from exc
            except PaperlessError as exc:
                raise UpstreamError(str(exc)) from exc
            for doc in page.results:
                # Do not create Atlas entities on search; assign creates on write.
                ref = self._get_external_reference(doc.id)
                meta = " · ".join(
                    part
                    for part in (doc.created_date, doc.correspondent, doc.document_type)
                    if part
                )
                hits.append(
                    EntitySearchHit(
                        id=str(ref.entity_id) if ref is not None else None,
                        label=doc.title or f"Document {doc.id}",
                        entity_type="document",
                        paperless_document_id=doc.id,
                        subtitle=meta or None,
                        open_url=self._settings.paperless_document_url(doc.id),
                    )
                )
        return hits[:limit]

    def bulk_add_relationships(
        self,
        paperless_document_ids: list[int],
        relationship_code: str,
        token: str | None = None,
        *,
        target: str | None = None,
        target_entity_id: str | None = None,
        target_paperless_id: int | None = None,
        strict: bool = False,
    ) -> list[BulkRelationshipResult]:
        auth = self._require_token(token)
        max_docs = self._settings.ingest_bulk_max_documents
        if not paperless_document_ids:
            raise ValidationError("paperless_document_ids must not be empty")
        if len(paperless_document_ids) > max_docs:
            raise ValidationError(f"At most {max_docs} documents per bulk request")
        provided = sum(
            1
            for value in (target, target_entity_id, target_paperless_id)
            if value is not None
        )
        if provided != 1:
            raise ValidationError(
                "Provide exactly one of target, target_entity_id, or target_paperless_id"
            )

        results: list[BulkRelationshipResult] = []
        for doc_id in paperless_document_ids:
            try:
                self._ensure_paperless_access(doc_id, auth)
                before = {
                    item.id
                    for item in self.get_document(doc_id, token=auth).relationships
                }
                document = self.add_document_relationship(
                    doc_id,
                    relationship_code,
                    token=auth,
                    target=target,
                    target_entity_id=target_entity_id,
                    target_paperless_id=target_paperless_id,
                )
                created_ids = [item.id for item in document.relationships if item.id not in before]
                results.append(
                    BulkRelationshipResult(
                        paperless_document_id=doc_id,
                        status="created",
                        relationship_id=created_ids[0] if created_ids else None,
                    )
                )
            except (ForbiddenDocumentError, NotFoundError):
                results.append(
                    BulkRelationshipResult(
                        paperless_document_id=doc_id,
                        status="forbidden_or_missing",
                    )
                )
                if strict:
                    break
            except ConflictError:
                results.append(
                    BulkRelationshipResult(
                        paperless_document_id=doc_id,
                        status="skipped_duplicate",
                    )
                )
                if strict:
                    break
            except ValidationError:
                results.append(
                    BulkRelationshipResult(
                        paperless_document_id=doc_id,
                        status="validation_error",
                    )
                )
                if strict:
                    break
        return results

    def search_concepts(
        self,
        *,
        q: str = "",
        ontology_code: str | None = None,
        limit: int = 25,
        token: str | None = None,
    ) -> list[ConceptView]:
        auth = self._require_token(token)
        self._validate_paperless_token(auth)
        if limit < 1:
            raise ValidationError("limit must be >= 1")
        query = select(Concept).options(joinedload(Concept.ontology))
        if ontology_code:
            ontology = self._session.scalar(select(Ontology).where(Ontology.code == ontology_code))
            if ontology is None:
                raise NotFoundError(f"Ontology '{ontology_code}' not found")
            query = query.where(Concept.ontology_id == ontology.id)
        needle = q.strip()
        if needle:
            escaped = (
                needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            pattern = f"%{escaped}%"
            query = query.where(
                or_(
                    Concept.code.ilike(pattern, escape="\\"),
                    Concept.name.ilike(pattern, escape="\\"),
                )
            )
        query = query.order_by(Concept.name).limit(limit)
        concepts = list(self._session.scalars(query).unique())
        return [ConceptView(code=item.code, name=item.name) for item in concepts]

    def add_document_relationship(
        self,
        paperless_document_id: int,
        relationship_code: str,
        token: str | None = None,
        *,
        target: str | None = None,
        target_entity_id: str | None = None,
        target_paperless_id: int | None = None,
        origin: RelationshipOrigin = RelationshipOrigin.manual,
        status: RelationshipStatus = RelationshipStatus.confirmed,
    ) -> DocumentSemantics:
        auth = self._require_token(token)
        self._ensure_paperless_access(paperless_document_id, auth)
        source_entity = self._get_or_create_document_entity(paperless_document_id)
        self.add_entity_relationship(
            str(source_entity.id),
            relationship_code,
            token=auth,
            target=target,
            target_entity_id=target_entity_id,
            target_paperless_id=target_paperless_id,
            origin=origin,
            status=status,
        )
        return self.get_document(paperless_document_id, token=auth)

    def add_relationship(
        self,
        paperless_document_id: int,
        relationship_code: str,
        target: str,
        token: str | None = None,
        *,
        origin: RelationshipOrigin = RelationshipOrigin.manual,
        status: RelationshipStatus = RelationshipStatus.confirmed,
        created_by: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        generated_at: datetime | None = None,
    ) -> DocumentSemantics:
        auth = self._require_token(token)
        self._ensure_paperless_access(paperless_document_id, auth)
        source_entity = self._get_or_create_document_entity(paperless_document_id)
        self.add_entity_relationship(
            str(source_entity.id),
            relationship_code,
            token=auth,
            target=target,
            origin=origin,
            status=status,
            created_by=created_by,
            model=model,
            prompt_version=prompt_version,
            generated_at=generated_at,
        )
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
                joinedload(Relationship.source_entity).joinedload(Entity.external_reference),
                joinedload(Relationship.target_entity).joinedload(Entity.external_reference),
                joinedload(Relationship.relationship_type).joinedload(
                    RelationshipType.inverse_relationship_type
                ),
            )
            .where(Relationship.id == rel_uuid)
        ).unique().one_or_none()
        if relationship is None:
            raise NotFoundError("Relationship not found")

        self._ensure_entity_readable(relationship.source_entity, auth)
        self._ensure_entity_readable(relationship.target_entity, auth)

        source_id = relationship.source_entity_id
        target_id = relationship.target_entity_id
        rel_type = relationship.relationship_type

        self._session.delete(relationship)
        self._session.flush()

        if rel_type.directionality == RelationshipDirectionality.symmetric:
            companion = self._find_edge(target_id, rel_type.id, source_id)
            if companion is not None:
                self._session.delete(companion)
                self._session.flush()

        inverse = rel_type.inverse_relationship_type
        if inverse is not None:
            companion = self._find_edge(target_id, inverse.id, source_id)
            if companion is not None:
                self._session.delete(companion)
                self._session.flush()

    def list_relationship_types(self, token: str | None = None) -> list[RelationshipTypeView]:
        auth = self._require_token(token)
        self._validate_paperless_token(auth)
        rows = self._session.scalars(
            select(RelationshipType).options(
                joinedload(RelationshipType.target_ontology),
                joinedload(RelationshipType.inverse_relationship_type),
            )
        ).unique()
        views = [
            RelationshipTypeView(
                code=item.code,
                name=item.name,
                target_ontology=item.target_ontology.code if item.target_ontology else None,
                directionality=item.directionality.value,
                inverse=(
                    item.inverse_relationship_type.code
                    if item.inverse_relationship_type
                    else None
                ),
            )
            for item in rows
        ]
        views.sort(key=lambda item: item.code)
        return views

    def list_ontology_codes(self) -> list[str]:
        codes = list(self._session.scalars(select(Ontology.code)))
        codes.sort()
        return codes

    def list_concepts(self, ontology_code: str, token: str | None = None) -> list[ConceptView]:
        auth = self._require_token(token)
        self._validate_paperless_token(auth)
        ontology = self._session.scalar(select(Ontology).where(Ontology.code == ontology_code))
        if ontology is None:
            raise NotFoundError(f"Ontology '{ontology_code}' not found")
        concepts = list(
            self._session.scalars(select(Concept).where(Concept.ontology_id == ontology.id))
        )
        concepts.sort(key=lambda item: item.name)
        return [ConceptView(code=item.code, name=item.name) for item in concepts]

    def list_paperless_external_references(self) -> list[ExternalReference]:
        return list(
            self._session.scalars(
                select(ExternalReference).where(
                    ExternalReference.system == EXTERNAL_SYSTEM_PAPERLESS
                )
            )
        )
