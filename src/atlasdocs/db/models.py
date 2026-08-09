from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(value: datetime) -> datetime:
    """Normalize SQLite-naive timestamps for comparison with aware utcnow()."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class EntityType(str, enum.Enum):
    document = "document"
    concept = "concept"


class RelationshipDirectionality(str, enum.Enum):
    directed = "directed"
    symmetric = "symmetric"


class RelationshipOrigin(str, enum.Enum):
    manual = "manual"
    import_ = "import"
    deterministic_rule = "deterministic-rule"
    llm = "llm"
    mcp = "mcp"


class RelationshipStatus(str, enum.Enum):
    suggested = "suggested"
    confirmed = "confirmed"


class IngestionJobState(str, enum.Enum):
    uploading = "UPLOADING"
    processing = "PROCESSING"
    resolving_document = "RESOLVING_DOCUMENT"
    retryable_failure = "RETRYABLE_FAILURE"
    ready = "READY"
    failed = "FAILED"


ENTITY_TYPE_ENUM = Enum(
    EntityType,
    name="entity_type",
    values_callable=lambda obj: [e.value for e in obj],
    native_enum=False,
    length=64,
)
DIRECTIONALITY_ENUM = Enum(
    RelationshipDirectionality,
    name="relationship_directionality",
    values_callable=lambda obj: [e.value for e in obj],
    native_enum=False,
    length=32,
)
ORIGIN_ENUM = Enum(
    RelationshipOrigin,
    name="relationship_origin",
    values_callable=lambda obj: [e.value for e in obj],
    native_enum=False,
    length=32,
)
STATUS_ENUM = Enum(
    RelationshipStatus,
    name="relationship_status",
    values_callable=lambda obj: [e.value for e in obj],
    native_enum=False,
    length=32,
)
INGESTION_STATE_ENUM = Enum(
    IngestionJobState,
    name="ingestion_job_state",
    values_callable=lambda obj: [e.value for e in obj],
    native_enum=False,
    length=32,
)

EXTERNAL_SYSTEM_PAPERLESS = "paperless"


def parse_relationship_origin(value: str) -> RelationshipOrigin:
    """Accept architecture vocabulary plus legacy ``rule`` from v0.1/v0.2."""
    if value == "rule":
        return RelationshipOrigin.deterministic_rule
    try:
        return RelationshipOrigin(value)
    except ValueError as exc:
        raise ValueError(f"Unknown relationship origin '{value}'") from exc


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[EntityType] = mapped_column(ENTITY_TYPE_ENUM, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    semantic_completeness: Mapped[str] = mapped_column(
        String(32), nullable=False, default="empty", server_default="empty"
    )

    external_reference: Mapped[ExternalReference | None] = relationship(
        back_populates="entity", uselist=False
    )
    concept: Mapped[Concept | None] = relationship(back_populates="entity", uselist=False)
    outgoing_relationships: Mapped[list[Relationship]] = relationship(
        back_populates="source_entity",
        foreign_keys="Relationship.source_entity_id",
    )
    incoming_relationships: Mapped[list[Relationship]] = relationship(
        back_populates="target_entity",
        foreign_keys="Relationship.target_entity_id",
    )


class ExternalReference(Base):
    __tablename__ = "external_references"
    __table_args__ = (
        UniqueConstraint("system", "external_id", name="uq_external_reference_system_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("entities.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    system: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    entity: Mapped[Entity] = relationship(back_populates="external_reference")


class Ontology(Base):
    __tablename__ = "ontologies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    concepts: Mapped[list[Concept]] = relationship(back_populates="ontology")


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("ontology_id", "code", name="uq_concept_ontology_code"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    ontology_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ontologies.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    entity: Mapped[Entity] = relationship(back_populates="concept")
    ontology: Mapped[Ontology] = relationship(back_populates="concepts")


class RelationshipType(Base):
    __tablename__ = "relationship_types"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_ontology_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ontologies.id", ondelete="RESTRICT"), nullable=True
    )
    directionality: Mapped[RelationshipDirectionality] = mapped_column(
        DIRECTIONALITY_ENUM,
        nullable=False,
        default=RelationshipDirectionality.directed,
    )
    inverse_relationship_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("relationship_types.id", ondelete="SET NULL"), nullable=True
    )
    source_entity_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    target_entity_types: Mapped[list | None] = mapped_column(JSON, nullable=True)

    target_ontology: Mapped[Ontology | None] = relationship()
    inverse_relationship_type: Mapped[RelationshipType | None] = relationship(
        remote_side=[id],
        foreign_keys=[inverse_relationship_type_id],
    )


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_entity_id",
            "relationship_type_id",
            "target_entity_id",
            name="uq_relationship_triple",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("relationship_types.id", ondelete="RESTRICT"), nullable=False
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    origin: Mapped[RelationshipOrigin] = mapped_column(
        ORIGIN_ENUM, nullable=False, default=RelationshipOrigin.manual
    )
    status: Mapped[RelationshipStatus] = mapped_column(
        STATUS_ENUM, nullable=False, default=RelationshipStatus.confirmed
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_entity: Mapped[Entity] = relationship(
        back_populates="outgoing_relationships",
        foreign_keys=[source_entity_id],
    )
    target_entity: Mapped[Entity] = relationship(
        back_populates="incoming_relationships",
        foreign_keys=[target_entity_id],
    )
    relationship_type: Mapped[RelationshipType] = relationship()


class UiSession(Base):
    __tablename__ = "ui_sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paperless_authorization_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    username_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def authenticated(self) -> bool:
        return bool(self.paperless_authorization_ciphertext)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    state: Mapped[IngestionJobState] = mapped_column(INGESTION_STATE_ENUM, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    user_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paperless_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    paperless_document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correlation_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolution_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
