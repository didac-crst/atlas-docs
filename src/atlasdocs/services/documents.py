from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from atlasdocs.db.models import (
    Concept,
    DocumentReference,
    Entity,
    Relationship,
    RelationshipOrigin,
    RelationshipStatus,
    RelationshipType,
)
from atlasdocs.services.paperless import (
    PaperlessAuthError,
    PaperlessClient,
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


@dataclass(frozen=True)
class RelationshipView:
    type: str
    target: str
    origin: str
    status: str


@dataclass(frozen=True)
class DocumentSemantics:
    paperless_document_id: int
    entity_id: str
    relationships: list[RelationshipView]


class DocumentService:
    def __init__(self, session: Session, paperless: PaperlessClient) -> None:
        self._session = session
        self._paperless = paperless

    def _ensure_paperless_access(self, paperless_document_id: int, token: str | None) -> None:
        try:
            self._paperless.assert_accessible(paperless_document_id, token=token)
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
        stmt = select(Concept).where(Concept.name == target)
        if relationship_type.target_ontology_id is not None:
            stmt = stmt.where(Concept.ontology_id == relationship_type.target_ontology_id)
        matches = list(self._session.scalars(stmt))
        if not matches:
            raise ValidationError(f"Unknown target concept '{target}'")
        if len(matches) > 1:
            raise ValidationError(f"Ambiguous target concept '{target}'")
        return matches[0]

    def get_document(
        self, paperless_document_id: int, token: str | None = None
    ) -> DocumentSemantics:
        self._ensure_paperless_access(paperless_document_id, token)
        reference = self._session.scalar(
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
        )
        if reference is None:
            # Accessible in Paperless but no semantics yet.
            return DocumentSemantics(
                paperless_document_id=paperless_document_id,
                entity_id="",
                relationships=[],
            )

        views = [
            RelationshipView(
                type=rel.relationship_type.code,
                target=rel.target_concept.name,
                origin=rel.origin.value,
                status=rel.status.value,
            )
            for rel in reference.entity.relationships
        ]
        views.sort(key=lambda item: (item.type, item.target))
        return DocumentSemantics(
            paperless_document_id=paperless_document_id,
            entity_id=str(reference.entity_id),
            relationships=views,
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
        self._ensure_paperless_access(paperless_document_id, token)

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

        return self.get_document(paperless_document_id, token=token)
