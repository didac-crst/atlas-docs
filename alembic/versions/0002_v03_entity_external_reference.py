"""v0.3 entity-first core: ExternalReference, concept entities, entity edges."""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_v03_entity_external_reference"
down_revision: Union[str, None] = "0001_v01_semantic_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fk_name(bind, table: str, column: str, fallback: str) -> str:
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table):
        if fk.get("constrained_columns") == [column]:
            name = fk.get("name")
            if name:
                return name
    return fallback


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("entities", sa.Column("entity_type", sa.String(length=64), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE entities
            SET entity_type = 'document'
            WHERE id IN (SELECT entity_id FROM document_references)
            """
        )
    )
    op.execute(sa.text("UPDATE entities SET entity_type = 'document' WHERE entity_type IS NULL"))
    with op.batch_alter_table("entities") as batch:
        batch.alter_column("entity_type", existing_type=sa.String(length=64), nullable=False)

    op.execute(
        sa.text(
            """
            INSERT INTO entities (id, entity_type, created_at)
            SELECT id, 'concept', CURRENT_TIMESTAMP FROM concepts
            """
        )
    )
    with op.batch_alter_table("concepts") as batch:
        batch.create_foreign_key(
            "fk_concepts_id_entities",
            "entities",
            ["id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.create_table(
        "external_references",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("system", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id"),
        sa.UniqueConstraint("system", "external_id", name="uq_external_reference_system_id"),
    )

    docs = bind.execute(
        sa.text(
            "SELECT entity_id, paperless_document_id, created_at FROM document_references"
        )
    ).fetchall()
    for entity_id, paperless_document_id, created_at in docs:
        bind.execute(
            sa.text(
                """
                INSERT INTO external_references (id, entity_id, system, external_id, created_at)
                VALUES (:id, :entity_id, 'paperless', :external_id, :created_at)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "entity_id": str(entity_id),
                "external_id": str(paperless_document_id),
                "created_at": created_at,
            },
        )

    op.add_column(
        "relationship_types",
        sa.Column("directionality", sa.String(length=32), nullable=True),
    )
    op.execute(sa.text("UPDATE relationship_types SET directionality = 'directed'"))
    op.add_column(
        "relationship_types",
        sa.Column("inverse_relationship_type_id", sa.Uuid(), nullable=True),
    )
    with op.batch_alter_table("relationship_types") as batch:
        batch.alter_column("directionality", existing_type=sa.String(length=32), nullable=False)
        batch.create_foreign_key(
            "fk_relationship_types_inverse",
            "relationship_types",
            ["inverse_relationship_type_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.add_column("relationships", sa.Column("target_entity_id", sa.Uuid(), nullable=True))
    op.execute(sa.text("UPDATE relationships SET target_entity_id = target_concept_id"))
    op.add_column("relationships", sa.Column("created_by", sa.String(length=255), nullable=True))
    op.add_column("relationships", sa.Column("model", sa.String(length=255), nullable=True))
    op.add_column("relationships", sa.Column("prompt_version", sa.String(length=128), nullable=True))
    op.add_column(
        "relationships",
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE relationships SET origin = 'deterministic-rule' WHERE origin = 'rule'"
        )
    )

    target_fk = _fk_name(
        bind, "relationships", "target_concept_id", "relationships_target_concept_id_fkey"
    )
    with op.batch_alter_table("relationships") as batch:
        batch.alter_column("target_entity_id", existing_type=sa.Uuid(), nullable=False)
        batch.drop_constraint("uq_relationship_triple", type_="unique")
        # SQLite 0001 FKs are unnamed; batch table recreate drops them with the column.
        if bind.dialect.name != "sqlite" and target_fk:
            batch.drop_constraint(target_fk, type_="foreignkey")
        batch.drop_column("target_concept_id")
        batch.create_foreign_key(
            "fk_relationships_target_entity",
            "entities",
            ["target_entity_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_unique_constraint(
            "uq_relationship_triple",
            ["source_entity_id", "relationship_type_id", "target_entity_id"],
        )

    op.drop_table("document_references")


def downgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "document_references",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("paperless_document_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id"),
        sa.UniqueConstraint("paperless_document_id"),
    )
    refs = bind.execute(
        sa.text(
            """
            SELECT id, entity_id, external_id, created_at
            FROM external_references
            WHERE system = 'paperless'
            """
        )
    ).fetchall()
    for ref_id, entity_id, external_id, created_at in refs:
        bind.execute(
            sa.text(
                """
                INSERT INTO document_references (id, entity_id, paperless_document_id, created_at)
                VALUES (:id, :entity_id, :paperless_document_id, :created_at)
                """
            ),
            {
                "id": str(ref_id),
                "entity_id": str(entity_id),
                "paperless_document_id": int(external_id),
                "created_at": created_at,
            },
        )

    op.add_column("relationships", sa.Column("target_concept_id", sa.Uuid(), nullable=True))
    op.execute(sa.text("UPDATE relationships SET target_concept_id = target_entity_id"))
    op.execute(
        sa.text(
            "UPDATE relationships SET origin = 'rule' WHERE origin = 'deterministic-rule'"
        )
    )

    with op.batch_alter_table("relationships") as batch:
        batch.drop_constraint("uq_relationship_triple", type_="unique")
        batch.drop_constraint("fk_relationships_target_entity", type_="foreignkey")
        batch.drop_column("target_entity_id")
        batch.drop_column("created_by")
        batch.drop_column("model")
        batch.drop_column("prompt_version")
        batch.drop_column("generated_at")
        batch.alter_column("target_concept_id", existing_type=sa.Uuid(), nullable=False)
        batch.create_foreign_key(
            "relationships_target_concept_id_fkey",
            "concepts",
            ["target_concept_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_unique_constraint(
            "uq_relationship_triple",
            ["source_entity_id", "relationship_type_id", "target_concept_id"],
        )

    with op.batch_alter_table("relationship_types") as batch:
        batch.drop_constraint("fk_relationship_types_inverse", type_="foreignkey")
        batch.drop_column("inverse_relationship_type_id")
        batch.drop_column("directionality")

    op.drop_table("external_references")

    with op.batch_alter_table("concepts") as batch:
        batch.drop_constraint("fk_concepts_id_entities", type_="foreignkey")

    op.execute(sa.text("DELETE FROM entities WHERE entity_type = 'concept'"))
    with op.batch_alter_table("entities") as batch:
        batch.drop_column("entity_type")
