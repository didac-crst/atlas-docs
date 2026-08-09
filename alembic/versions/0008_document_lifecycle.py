"""Add entity tombstones, replacement history, and replace ingestion jobs."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_document_lifecycle"
down_revision: Union[str, None] = "0007_semantic_completeness_constraints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("entities", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("entities", sa.Column("deleted_by_label", sa.String(length=255), nullable=True))
    op.create_index("ix_entities_deleted_at", "entities", ["deleted_at"])

    op.create_table(
        "document_replacement_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("previous_external_id", sa.String(length=255), nullable=False),
        sa.Column("new_external_id", sa.String(length=255), nullable=False),
        sa.Column("previous_checksum", sa.String(length=64), nullable=True),
        sa.Column("new_checksum", sa.String(length=64), nullable=True),
        sa.Column("actor_label", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_replacement_history_entity_id",
        "document_replacement_history",
        ["entity_id"],
    )

    with op.batch_alter_table("ingestion_jobs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "job_kind",
                sa.Enum(
                    "ingest",
                    "replace",
                    name="ingestion_job_kind",
                    native_enum=False,
                    length=32,
                ),
                nullable=False,
                server_default="ingest",
            )
        )
        batch_op.add_column(sa.Column("replace_of_entity_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("replace_reason", sa.String(length=512), nullable=True))
        batch_op.create_foreign_key(
            "fk_ingestion_jobs_replace_of_entity_id",
            "entities",
            ["replace_of_entity_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("ingestion_jobs") as batch_op:
        batch_op.drop_constraint("fk_ingestion_jobs_replace_of_entity_id", type_="foreignkey")
        batch_op.drop_column("replace_reason")
        batch_op.drop_column("replace_of_entity_id")
        batch_op.drop_column("job_kind")
    op.drop_index(
        "ix_document_replacement_history_entity_id",
        table_name="document_replacement_history",
    )
    op.drop_table("document_replacement_history")
    op.drop_index("ix_entities_deleted_at", table_name="entities")
    op.drop_column("entities", "deleted_by_label")
    op.drop_column("entities", "deleted_at")
