from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RelationshipOrigin(str, enum.Enum):
    manual = "manual"
    rule = "rule"
    import_ = "import"
    llm = "llm"


class RelationshipStatus(str, enum.Enum):
    suggested = "suggested"
    confirmed = "confirmed"


# Store enum values as strings for PostgreSQL + SQLite test portability.
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


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document_reference: Mapped[DocumentReference | None] = relationship(
        back_populates="entity", uselist=False
    )
    relationships: Mapped[list[Relationship]] = relationship(back_populates="source_entity")


class DocumentReference(Base):
    __tablename__ = "document_references"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("entities.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    paperless_document_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    entity: Mapped[Entity] = relationship(back_populates="document_reference")


class Ontology(Base):
    __tablename__ = "ontologies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    concepts: Mapped[list[Concept]] = relationship(back_populates="ontology")


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("ontology_id", "code", name="uq_concept_ontology_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ontology_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ontologies.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    ontology: Mapped[Ontology] = relationship(back_populates="concepts")


class RelationshipType(Base):
    __tablename__ = "relationship_types"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_ontology_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ontologies.id", ondelete="RESTRICT"), nullable=True
    )

    target_ontology: Mapped[Ontology | None] = relationship()


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_entity_id",
            "relationship_type_id",
            "target_concept_id",
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
    target_concept_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("concepts.id", ondelete="RESTRICT"), nullable=False
    )
    origin: Mapped[RelationshipOrigin] = mapped_column(
        ORIGIN_ENUM, nullable=False, default=RelationshipOrigin.manual
    )
    status: Mapped[RelationshipStatus] = mapped_column(
        STATUS_ENUM, nullable=False, default=RelationshipStatus.confirmed
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source_entity: Mapped[Entity] = relationship(back_populates="relationships")
    relationship_type: Mapped[RelationshipType] = relationship()
    target_concept: Mapped[Concept] = relationship()
