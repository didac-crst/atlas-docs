"""Add lifecycle_category and Master Data archive/redirect fields."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_lifecycle_categories"
down_revision: Union[str, None] = "0009_backfill_semantic_completeness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("entities") as batch_op:
        batch_op.add_column(
            sa.Column(
                "lifecycle_category",
                sa.String(length=32),
                nullable=False,
                server_default="master_data",
            )
        )
        batch_op.create_index(
            "ix_entities_lifecycle_category",
            ["lifecycle_category"],
        )
        batch_op.add_column(
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("trashed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("display_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("merged_into_entity_id", sa.Uuid(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_entities_merged_into_entity_id",
            "entities",
            ["merged_into_entity_id"],
            ["id"],
            ondelete="SET NULL",
        )

    conn = op.get_bind()
    # Documents are Evidence; cases are Organizational; everything else Master Data.
    conn.execute(
        sa.text(
            """
            UPDATE entities
            SET lifecycle_category = 'evidence'
            WHERE entity_type = 'document'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE entities
            SET lifecycle_category = 'organizational'
            WHERE id IN (
                SELECT c.id FROM concepts c
                JOIN ontologies o ON o.id = c.ontology_id
                WHERE o.code = 'case'
            )
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("entities") as batch_op:
        batch_op.drop_constraint(
            "fk_entities_merged_into_entity_id", type_="foreignkey"
        )
        batch_op.drop_column("merged_into_entity_id")
        batch_op.drop_column("display_name")
        batch_op.drop_column("trashed_at")
        batch_op.drop_column("archived_at")
        batch_op.drop_index("ix_entities_lifecycle_category")
        batch_op.drop_column("lifecycle_category")
