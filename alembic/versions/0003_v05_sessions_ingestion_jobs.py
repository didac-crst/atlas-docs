"""v0.5 durable UI sessions and ingestion jobs."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_v05_sessions_ingestion_jobs"
down_revision: Union[str, None] = "0002_v03_entity_external_reference"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ui_sessions",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("csrf_token", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paperless_authorization_ciphertext", sa.Text(), nullable=True),
        sa.Column("token_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("username_label", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ui_sessions_expires_at", "ui_sessions", ["expires_at"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_label", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("token_ciphertext", sa.Text(), nullable=True),
        sa.Column("token_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("content_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("paperless_task_id", sa.String(length=128), nullable=True),
        sa.Column("paperless_document_id", sa.Integer(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("entity_id", sa.Uuid(), sa.ForeignKey("entities.id", ondelete="SET NULL")),
    )
    op.create_index(
        "ix_ingestion_jobs_state_next_attempt",
        "ingestion_jobs",
        ["state", "next_attempt_at"],
    )
    op.create_index(
        "ix_ingestion_jobs_fingerprint_sha",
        "ingestion_jobs",
        ["token_fingerprint", "content_sha256"],
    )
    op.create_index(
        "ix_ingestion_jobs_fingerprint_created",
        "ingestion_jobs",
        ["token_fingerprint", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_fingerprint_created", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_fingerprint_sha", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_state_next_attempt", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index("ix_ui_sessions_expires_at", table_name="ui_sessions")
    op.drop_table("ui_sessions")
