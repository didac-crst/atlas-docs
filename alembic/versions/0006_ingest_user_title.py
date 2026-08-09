"""Add optional user_title for Paperless ingest (no UUID titles)."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_ingest_user_title"
down_revision: Union[str, None] = "0005_ingest_resolve_states"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column("user_title", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "user_title")
