"""Add semantic completeness and relationship entity-type constraints."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_semantic_completeness_constraints"
down_revision: Union[str, None] = "0006_ingest_user_title"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "entities",
        sa.Column(
            "semantic_completeness",
            sa.String(length=32),
            nullable=False,
            server_default="empty",
        ),
    )
    op.create_index(
        "ix_entities_semantic_completeness",
        "entities",
        ["semantic_completeness"],
    )
    op.add_column(
        "relationship_types",
        sa.Column("source_entity_types", sa.JSON(), nullable=True),
    )
    op.add_column(
        "relationship_types",
        sa.Column("target_entity_types", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("relationship_types", "target_entity_types")
    op.drop_column("relationship_types", "source_entity_types")
    op.drop_index("ix_entities_semantic_completeness", table_name="entities")
    op.drop_column("entities", "semantic_completeness")
