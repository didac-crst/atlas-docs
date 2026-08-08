from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
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
    directionality: str
    inverse: str | None


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

    def _paperless_external_id(self, paperless_document_id: int) -> str:
        return str(paperless_document_id)

    def _get_external_reference(self, paperless_document_id: int) -> ExternalReference | None:
        return self._session.scalar(
            select(ExternalReference).where(
                ExternalReference.system == EXTERNAL_SYSTEM_PAPERLESS,
                ExternalReference.external_id == self._paperless_external_id(paperless_document_id),
            )
        )

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

    def _target_label(self, relationship: Relationship) -> str:
        concept = relationship.target_entity.concept
        if concept is not None:
            return concept.name
        external = relationship.target_entity.external_reference
        if external is not None:
            return f"{external.system}:{external.external_id}"
        return str(relationship.target_entity_id)

    def _relationship_views(self, entity: Entity | None) -> list[RelationshipView]:
        if entity is None:
            return []
        views = [
            RelationshipView(
                id=str(rel.id),
                type=rel.relationship_type.code,
                target=self._target_label(rel),
                origin=rel.origin.value,
                status=rel.status.value,
            )
            for rel in entity.outgoing_relationships
        ]
        views.sort(key=lambda item: (item.type, item.target))
        return views

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
        generated_at,
        require_new: bool,
    ) -> Relationship:
        existing = self._find_edge(source_entity_id, relationship_type_id, target_entity_id)
        if existing is not None:
            if require_new:
                raise ConflictError(
                    "Relationship already exists for this document, type, and target"
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
                    "Relationship already exists for this document, type, and target"
                ) from exc
            existing = self._find_edge(source_entity_id, relationship_type_id, target_entity_id)
            if existing is None:
                raise
            return existing

    def get_document(self, paperless_document_id: int, token: str | None = None) -> DocumentSemantics:
        auth = self._require_token(token)
        paperless_doc = self._ensure_paperless_access(paperless_document_id, auth)
        reference = self._session.scalars(
            select(ExternalReference)
            .options(
                joinedload(ExternalReference.entity)
                .joinedload(Entity.outgoing_relationships)
                .joinedload(Relationship.relationship_type),
                joinedload(ExternalReference.entity)
                .joinedload(Entity.outgoing_relationships)
                .joinedload(Relationship.target_entity)
                .joinedload(Entity.concept),
                joinedload(ExternalReference.entity)
                .joinedload(Entity.outgoing_relationships)
                .joinedload(Relationship.target_entity)
                .joinedload(Entity.external_reference),
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
        generated_at=None,
    ) -> DocumentSemantics:
        auth = self._require_token(token)
        self._ensure_paperless_access(paperless_document_id, auth)

        relationship_type = self._session.scalar(
            select(RelationshipType)
            .options(joinedload(RelationshipType.inverse_relationship_type))
            .where(RelationshipType.code == relationship_code)
        )
        if relationship_type is None:
            raise ValidationError(f"Unknown relationship type '{relationship_code}'")

        concept = self._resolve_target_concept(relationship_type, target)
        source_entity = self._get_or_create_document_entity(paperless_document_id)

        self._ensure_edge(
            source_entity_id=source_entity.id,
            relationship_type_id=relationship_type.id,
            target_entity_id=concept.id,
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
                source_entity_id=concept.id,
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
                source_entity_id=concept.id,
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
                joinedload(Relationship.relationship_type).joinedload(
                    RelationshipType.inverse_relationship_type
                ),
            )
            .where(Relationship.id == rel_uuid)
        ).unique().one_or_none()
        if relationship is None or relationship.source_entity.external_reference is None:
            raise NotFoundError("Relationship not found")

        external = relationship.source_entity.external_reference
        if external.system != EXTERNAL_SYSTEM_PAPERLESS:
            raise NotFoundError("Relationship not found")
        paperless_id = int(external.external_id)
        self._ensure_paperless_access(paperless_id, auth)

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

    def list_relationship_types(self) -> list[RelationshipTypeView]:
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

    def list_concepts(self, ontology_code: str) -> list[ConceptView]:
        ontology = self._session.scalar(select(Ontology).where(Ontology.code == ontology_code))
        if ontology is None:
            raise NotFoundError(f"Ontology '{ontology_code}' not found")
        concepts = list(
            self._session.scalars(select(Concept).where(Concept.ontology_id == ontology.id))
        )
        concepts.sort(key=lambda item: item.name)
        return [ConceptView(code=item.code, name=item.name) for item in concepts]
