"""Durable async document ingestion (Paperless post_document + task poll)."""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from atlasdocs.config import get_settings
from atlasdocs.db.models import IngestionJob, IngestionJobState, as_aware, utcnow
from atlasdocs.security.tokens import decrypt_token, encrypt_token, token_fingerprint
from atlasdocs.services.documents import (
    ConflictError,
    DocumentService,
    UnauthorizedError,
    ValidationError,
)
from atlasdocs.services.paperless import (
    PaperlessAuthError,
    PaperlessClient,
    PaperlessDuplicateError,
    PaperlessUnavailableError,
)


@dataclass(frozen=True)
class IngestionJobView:
    id: str
    state: str
    created_at: datetime
    updated_at: datetime
    paperless_document_id: int | None
    paperless_task_id: str | None
    error_code: str | None
    error_message: str | None
    original_filename: str
    content_sha256: str


def spool_dir() -> Path:
    root = Path(tempfile.gettempdir()) / "atlasdocs-ingest"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    return root


def spool_path_for(job_id: uuid.UUID) -> Path:
    return spool_dir() / str(job_id)


def _safe_basename(filename: str | None) -> str:
    name = Path(filename or "upload.bin").name.strip() or "upload.bin"
    return name[:512]


def _job_view(job: IngestionJob) -> IngestionJobView:
    return IngestionJobView(
        id=str(job.id),
        state=job.state.value if isinstance(job.state, IngestionJobState) else str(job.state),
        created_at=job.created_at,
        updated_at=job.updated_at,
        paperless_document_id=job.paperless_document_id,
        paperless_task_id=job.paperless_task_id,
        error_code=job.error_code,
        error_message=job.error_message,
        original_filename=job.original_filename,
        content_sha256=job.content_sha256,
    )


class DuplicateIngestError(ConflictError):
    def __init__(self, message: str, *, paperless_document_id: int | None = None) -> None:
        super().__init__(message)
        self.paperless_document_id = paperless_document_id


class IngestionService:
    def __init__(self, session: Session, paperless: PaperlessClient) -> None:
        self._session = session
        self._paperless = paperless
        self._settings = get_settings()
        self._documents = DocumentService(session, paperless)

    def enqueue(
        self,
        *,
        authorization: str,
        filename: str,
        file_obj,
        content_type: str = "application/octet-stream",
        session_id: str | None = None,
        created_by_label: str | None = None,
    ) -> IngestionJobView:
        if not authorization:
            raise UnauthorizedError("Authorization required")
        max_bytes = self._settings.ingest_max_upload_bytes
        job_id = uuid.uuid4()
        path = spool_path_for(job_id)
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("wb") as out:
                while True:
                    chunk = file_obj.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValidationError(
                            f"Upload exceeds maximum size of {max_bytes} bytes"
                        )
                    digest.update(chunk)
                    out.write(chunk)
            if size == 0:
                raise ValidationError("Empty upload")
            sha = digest.hexdigest()
            fingerprint = token_fingerprint(authorization)
            existing = self._find_duplicate(fingerprint, sha, authorization)
            if existing is not None:
                raise DuplicateIngestError(
                    "Duplicate content already ingested",
                    paperless_document_id=existing,
                )
            job = IngestionJob(
                id=job_id,
                state=IngestionJobState.uploading,
                created_by_label=created_by_label,
                session_id=session_id,
                token_ciphertext=encrypt_token(
                    authorization, key=self._settings.token_encryption_key
                ),
                token_fingerprint=fingerprint,
                original_filename=_safe_basename(filename),
                content_sha256=sha,
                content_size_bytes=size,
                attempt_count=0,
                next_attempt_at=utcnow(),
            )
            self._session.add(job)
            self._session.flush()
            return _job_view(job)
        except Exception:
            if path.exists():
                path.unlink(missing_ok=True)
            raise

    def _find_duplicate(
        self, fingerprint: str, sha256: str, authorization: str
    ) -> int | None:
        row = self._session.scalar(
            select(IngestionJob)
            .where(
                IngestionJob.token_fingerprint == fingerprint,
                IngestionJob.content_sha256 == sha256,
                IngestionJob.state == IngestionJobState.ready,
                IngestionJob.paperless_document_id.is_not(None),
            )
            .order_by(IngestionJob.created_at.desc())
        )
        if row is None or row.paperless_document_id is None:
            return None
        try:
            self._paperless.assert_accessible(row.paperless_document_id, authorization)
        except PaperlessAuthError:
            return None
        except Exception:
            return None
        return row.paperless_document_id

    def list_jobs(self, authorization: str, *, limit: int = 50) -> list[IngestionJobView]:
        fingerprint = token_fingerprint(authorization)
        rows = self._session.scalars(
            select(IngestionJob)
            .where(IngestionJob.token_fingerprint == fingerprint)
            .order_by(IngestionJob.created_at.desc())
            .limit(limit)
        ).all()
        return [_job_view(row) for row in rows]

    def get_job(self, job_id: str, authorization: str) -> IngestionJobView:
        from atlasdocs.services.documents import NotFoundError

        try:
            uid = uuid.UUID(job_id)
        except ValueError as exc:
            raise ValidationError("Invalid job id") from exc
        job = self._session.get(IngestionJob, uid)
        if job is None or job.token_fingerprint != token_fingerprint(authorization):
            raise NotFoundError("Job not found")
        return _job_view(job)


class IngestionWorker:
    """Claim and process durable ingestion jobs."""

    def __init__(
        self,
        session: Session,
        paperless: PaperlessClient,
        *,
        worker_id: str | None = None,
        poll_sleep_seconds: float = 0.05,
    ) -> None:
        self._session = session
        self._paperless = paperless
        self._settings = get_settings()
        self._documents = DocumentService(session, paperless)
        self._worker_id = worker_id or f"worker-{os.getpid()}"
        self._poll_sleep = poll_sleep_seconds

    def run_once(self) -> bool:
        """Process at most one job. Returns True if work was done."""
        job = self._claim_job()
        if job is None:
            return False
        job_id = job.id
        # Persist the lease before any Paperless I/O so a crash mid-call cannot
        # leave the job unlocked for a second worker while upload is in flight.
        self._session.commit()
        try:
            job = self._session.get(IngestionJob, job_id)
            if job is None:
                return True
            self._process(job)
            self._session.commit()
        except Exception:
            self._session.rollback()
            try:
                job = self._session.get(IngestionJob, job_id)
                if job is not None and job.state in {
                    IngestionJobState.uploading,
                    IngestionJobState.processing,
                }:
                    self._fail(job, "worker_error", "Unhandled worker error")
                    self._session.commit()
            except Exception:
                self._session.rollback()
            raise
        return True

    def run_forever(self, *, idle_sleep: float = 1.0) -> None:
        while True:
            try:
                worked = self.run_once()
            except Exception:
                # Keep the worker alive; the failed job is terminal or reclaimed by lease.
                worked = False
            if not worked:
                time.sleep(idle_sleep)

    def _claim_job(self) -> IngestionJob | None:
        now = utcnow()
        lease_cutoff = now - timedelta(seconds=self._settings.ingest_lease_seconds)
        stmt = (
            select(IngestionJob)
            .where(
                IngestionJob.state.in_(
                    [IngestionJobState.uploading, IngestionJobState.processing]
                ),
                or_(
                    IngestionJob.next_attempt_at.is_(None),
                    IngestionJob.next_attempt_at <= now,
                ),
                or_(
                    IngestionJob.locked_at.is_(None),
                    IngestionJob.locked_at < lease_cutoff,
                ),
            )
            .order_by(IngestionJob.created_at.asc())
            .limit(1)
        )
        bind = self._session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        job = self._session.scalars(stmt).first()
        if job is None:
            return None
        job.locked_at = now
        job.locked_by = self._worker_id
        job.updated_at = now
        self._session.flush()
        return job

    def _process(self, job: IngestionJob) -> None:
        if not job.token_ciphertext:
            self._fail(job, "missing_token", "Job token unavailable")
            return
        try:
            authorization = decrypt_token(
                job.token_ciphertext, key=self._settings.token_encryption_key
            )
        except ValueError:
            self._fail(job, "token_decrypt_failed", "Unable to decrypt job token")
            return

        if job.state == IngestionJobState.uploading:
            self._forward_upload(job, authorization)
            if job.state == IngestionJobState.failed:
                return
        if job.state == IngestionJobState.processing:
            self._poll_task(job, authorization)

    def _forward_upload(self, job: IngestionJob, authorization: str) -> None:
        path = spool_path_for(job.id)
        if not path.exists():
            self._fail(job, "spool_missing", "Upload spool missing")
            return
        job.attempt_count += 1
        try:
            with path.open("rb") as handle:
                task_id = self._paperless.post_document(
                    authorization,
                    filename=job.original_filename,
                    content=handle,
                )
            job.paperless_task_id = task_id
            job.state = IngestionJobState.processing
            job.updated_at = utcnow()
            job.error_code = None
            job.error_message = None
            job.next_attempt_at = utcnow()
            path.unlink(missing_ok=True)
            self._session.flush()
        except PaperlessDuplicateError:
            path.unlink(missing_ok=True)
            self._fail(job, "duplicate", "Paperless rejected duplicate document")
        except PaperlessAuthError:
            path.unlink(missing_ok=True)
            self._fail(job, "paperless_unauthorized", "Paperless authorization failed")
        except PaperlessUnavailableError as exc:
            if job.attempt_count >= self._settings.ingest_max_attempts:
                path.unlink(missing_ok=True)
                self._fail(job, "upstream_error", str(exc)[:500])
            else:
                delay = min(60, 2 ** job.attempt_count)
                job.next_attempt_at = utcnow() + timedelta(seconds=delay)
                job.locked_at = None
                job.locked_by = None
                job.updated_at = utcnow()
                self._session.flush()
        except Exception as exc:  # noqa: BLE001 — terminal unexpected
            path.unlink(missing_ok=True)
            self._fail(job, "upload_failed", str(exc)[:500])

    def _poll_task(self, job: IngestionJob, authorization: str) -> None:
        if not job.paperless_task_id:
            self._fail(job, "missing_task", "Missing Paperless task id")
            return
        if as_aware(job.created_at) + timedelta(
            seconds=self._settings.ingest_processing_timeout_seconds
        ) < utcnow():
            self._fail(job, "processing_timeout", "Processing timed out")
            return
        try:
            status = self._paperless.get_task(job.paperless_task_id, authorization)
        except PaperlessAuthError:
            self._fail(job, "paperless_unauthorized", "Paperless authorization failed")
            return
        except PaperlessUnavailableError:
            job.next_attempt_at = utcnow() + timedelta(seconds=2)
            job.locked_at = None
            job.locked_by = None
            job.updated_at = utcnow()
            self._session.flush()
            return

        if status.status in {"PENDING", "STARTED", "RETRY", "RECEIVED"}:
            job.next_attempt_at = utcnow() + timedelta(seconds=1)
            job.locked_at = None
            job.locked_by = None
            job.updated_at = utcnow()
            self._session.flush()
            return

        if status.status == "FAILURE":
            msg = (status.result or "Paperless task failed")[:500]
            self._fail(job, "paperless_task_failed", msg)
            return

        if status.status == "SUCCESS":
            doc_id = status.related_document_id
            if doc_id is None:
                self._fail(job, "missing_document", "Task succeeded without document id")
                return
            try:
                self._paperless.assert_accessible(doc_id, authorization)
            except PaperlessAuthError:
                self._fail(job, "paperless_unauthorized", "Document inaccessible after consume")
                return
            entity = self._documents.get_or_create_document_entity(doc_id)
            job.paperless_document_id = doc_id
            job.entity_id = entity.id
            job.state = IngestionJobState.ready
            job.token_ciphertext = None
            job.locked_at = None
            job.locked_by = None
            job.updated_at = utcnow()
            job.error_code = None
            job.error_message = None
            self._session.flush()
            return

        self._fail(job, "unknown_task_status", f"Unexpected task status {status.status}")

    def _fail(self, job: IngestionJob, code: str, message: str) -> None:
        job.state = IngestionJobState.failed
        job.error_code = code[:64]
        job.error_message = message[:512]
        job.token_ciphertext = None
        job.locked_at = None
        job.locked_by = None
        job.updated_at = utcnow()
        spool_path_for(job.id).unlink(missing_ok=True)
        self._session.flush()
