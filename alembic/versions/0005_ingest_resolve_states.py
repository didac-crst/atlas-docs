"""Extend ingestion jobs for document resolution and spool retention."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_ingest_resolve_states"
down_revision: Union[str, None] = "0004_ingest_processing_started_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column("correlation_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "resolution_attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column("resolution_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_ingestion_jobs_correlation_key",
        "ingestion_jobs",
        ["correlation_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_correlation_key", table_name="ingestion_jobs")
    op.drop_column("ingestion_jobs", "resolution_started_at")
    op.drop_column("ingestion_jobs", "resolution_attempt_count")
    op.drop_column("ingestion_jobs", "correlation_key")
