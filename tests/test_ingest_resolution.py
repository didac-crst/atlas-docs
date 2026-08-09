"""Ingest FSM resolution, spool retention, retry, and redaction tests."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from atlasdocs.config import get_settings
from atlasdocs.db.models import Entity, ExternalReference, IngestionJob, IngestionJobState, as_aware, utcnow
from atlasdocs.db.session import get_session_factory
from atlasdocs.services.documents import DocumentService
from atlasdocs.services.ingest import (
    IngestionService,
    IngestionWorker,
    correlation_key_for,
    spool_path_for,
)
from atlasdocs.services.paperless import PaperlessClient, PaperlessUnavailableError
from tests.fakes import FakePaperlessTransport


def _connect(client: TestClient, token: str = "test-token") -> str:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    response = client.post(
        "/ui/api/connect",
        json={"csrf_token": csrf, "paperless_token": token},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _enqueue(client: TestClient, *, filename: str = "note.pdf", content: bytes = b"%PDF-hello") -> uuid.UUID:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    upload = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        files={"document": (filename, content, "application/pdf")},
    )
    assert upload.status_code == 202
    return uuid.UUID(upload.json()["id"])


def _worker(
    db,
    transport: FakePaperlessTransport,
    *,
    worker_id: str | None = None,
) -> IngestionWorker:
    return IngestionWorker(
        db,
        PaperlessClient(base_url="http://paperless.test", transport=transport),
        worker_id=worker_id,
    )


def test_task_success_with_related_document_ready_deletes_spool(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        assert spool_path_for(job_id).exists()
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.ready
        assert job.paperless_document_id is not None
        assert not spool_path_for(job_id).exists()
        assert job.token_ciphertext is None
    finally:
        db.close()


def test_task_success_with_result_data_document_id(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.success_document_id_in_result_data = True
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.ready
        assert job.paperless_document_id is not None
        assert not spool_path_for(job_id).exists()
    finally:
        db.close()


def test_task_success_without_id_enters_resolving_document(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.omit_related_document_on_success = True
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.resolving_document
        assert job.paperless_document_id is None
        assert spool_path_for(job_id).exists()
        assert job.token_ciphertext
    finally:
        db.close()


def test_upload_omits_paperless_title_by_default(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.ready
        upload = paperless_transport.uploaded_files[-1]
        assert upload["title"] is None
        assert not str(upload.get("title") or "").startswith("atlasdocs:")
        assert job.user_title is None
        assert job.correlation_key == correlation_key_for(job_id)
    finally:
        db.close()


def test_upload_preserves_user_supplied_title(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    upload = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        data={"title": "  Quarterly invoice  "},
        files={"document": ("note.pdf", b"%PDF-hello", "application/pdf")},
    )
    assert upload.status_code == 202
    job_id = uuid.UUID(upload.json()["id"])
    assert upload.json()["user_title"] == "Quarterly invoice"
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.ready
        assert job.user_title == "Quarterly invoice"
        assert paperless_transport.uploaded_files[-1]["title"] == "Quarterly invoice"
        assert not str(paperless_transport.uploaded_files[-1]["title"]).startswith("atlasdocs:")
    finally:
        db.close()


def test_resolving_without_task_document_id_does_not_use_title_guess(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.omit_related_document_on_success = True
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.resolving_document

        # Even if a document happens to share the internal correlation key as title,
        # AtlasDocs must not bind via title search anymore.
        upload = paperless_transport.uploaded_files[-1]
        paperless_transport.documents[upload["document_id"]]["title"] = correlation_key_for(job_id)
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        job.locked_by = None
        db.commit()

        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.resolving_document
        assert job.paperless_document_id is None
        assert spool_path_for(job_id).exists()
    finally:
        db.close()


def test_resolving_binds_when_task_later_exposes_document_id(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.omit_related_document_on_success = True
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.resolving_document
        upload = paperless_transport.uploaded_files[-1]
        doc_id = upload["document_id"]
        paperless_transport.tasks[job.paperless_task_id]["related_document_ids"] = [doc_id]
        paperless_transport.tasks[job.paperless_task_id]["result_data"] = {"document_id": doc_id}
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        job.locked_by = None
        db.commit()

        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.ready
        assert job.paperless_document_id == doc_id
        assert not spool_path_for(job_id).exists()
    finally:
        db.close()


def test_entity_binding_idempotent_on_repeat_ready(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.ready
        doc_id = job.paperless_document_id
        entity_id = job.entity_id
        assert doc_id is not None and entity_id is not None
        docs = DocumentService(
            db, PaperlessClient(base_url="http://paperless.test", transport=paperless_transport)
        )
        again = docs.get_or_create_document_entity(doc_id)
        assert again.id == entity_id
        refs = db.scalars(
            select(ExternalReference).where(ExternalReference.entity_id == entity_id)
        ).all()
        assert len(refs) == 1
    finally:
        db.close()


def test_resolution_timeout_retryable_failure_retains_spool_and_token(
    client: TestClient, paperless_transport: FakePaperlessTransport, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INGEST_RESOLUTION_TIMEOUT_SECONDS", "1")
    get_settings.cache_clear()
    paperless_transport.omit_related_document_on_success = True
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.resolving_document
        cipher = job.token_ciphertext
        job.resolution_started_at = utcnow() - timedelta(seconds=5)
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        job.locked_by = None
        db.commit()

        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.retryable_failure
        assert job.error_code == "missing_document"
        assert spool_path_for(job_id).exists()
        assert job.token_ciphertext == cipher
    finally:
        db.close()


def test_paperless_task_failure_is_terminal(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.task_auto_succeed = False
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.processing
        paperless_transport.tasks[job.paperless_task_id]["status"] = "FAILURE"
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        job.locked_by = None
        db.commit()

        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.failed
        assert job.error_code == "paperless_task_failed"
        assert job.token_ciphertext is None
        assert not spool_path_for(job_id).exists()
    finally:
        db.close()


def test_worker_restart_with_task_id_does_not_repost(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.task_auto_succeed = False
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        job = db.get(IngestionJob, job_id)
        assert job is not None
        worker = _worker(db, paperless_transport, worker_id="first")
        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.processing
        assert job.paperless_task_id
        uploads_after_first = len(paperless_transport.uploaded_files)

        job.state = IngestionJobState.uploading
        job.processing_started_at = utcnow()
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        job.locked_by = None
        db.commit()

        restart_worker = _worker(db, paperless_transport, worker_id="restart")
        assert restart_worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.processing
        assert len(paperless_transport.uploaded_files) == uploads_after_first
    finally:
        db.close()


def test_second_worker_skips_fresh_lease(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        job = db.get(IngestionJob, job_id)
        assert job is not None
        job.locked_at = utcnow()
        job.locked_by = "busy-worker"
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        db.commit()

        worker = _worker(db, paperless_transport, worker_id="second")
        assert worker.run_once() is False
    finally:
        db.close()


def test_spool_retained_through_processing_deleted_at_ready(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.task_auto_succeed = False
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.processing
        assert spool_path_for(job_id).exists()

        paperless_transport.tasks[job.paperless_task_id]["status"] = "SUCCESS"
        paperless_transport.tasks[job.paperless_task_id]["related_document"] = 901
        paperless_transport.documents[901] = {"id": 901, "title": "done", "created_date": "2024-06-01"}
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        job.locked_by = None
        db.commit()

        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.ready
        assert not spool_path_for(job_id).exists()
    finally:
        db.close()


def test_no_duplicate_paperless_submission_when_task_id_set(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        uploads = len(paperless_transport.uploaded_files)

        job = db.get(IngestionJob, job_id)
        assert job is not None
        job.state = IngestionJobState.uploading
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        job.locked_by = None
        db.commit()

        assert worker.run_once() is True
        assert len(paperless_transport.uploaded_files) == uploads
    finally:
        db.close()


def test_idempotent_entity_binding_on_complete(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        doc_id = job.paperless_document_id
        entity_id = job.entity_id
        assert doc_id is not None
        assert entity_id is not None

        service = DocumentService(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        again = service.get_or_create_document_entity(doc_id)
        assert again.id == entity_id
        count = db.query(Entity).join(ExternalReference).filter(
            ExternalReference.external_id == str(doc_id)
        ).count()
        assert count == 1
    finally:
        db.close()


def test_retry_job_from_retryable_failure_with_task_id(
    client: TestClient, paperless_transport: FakePaperlessTransport, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INGEST_RESOLUTION_TIMEOUT_SECONDS", "1")
    get_settings.cache_clear()
    paperless_transport.omit_related_document_on_success = True
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        job.resolution_started_at = utcnow() - timedelta(seconds=5)
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        job.locked_by = None
        db.commit()
        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.retryable_failure
        task_id = job.paperless_task_id

        service = IngestionService(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        retried = service.retry_job(str(job_id), "Token test-token")
        assert retried.state == "RESOLVING_DOCUMENT"
        db.refresh(job)
        assert job.paperless_task_id == task_id
    finally:
        db.close()


def test_retry_job_without_task_id_returns_uploading(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        job = db.get(IngestionJob, job_id)
        assert job is not None
        job.state = IngestionJobState.retryable_failure
        job.paperless_task_id = None
        job.error_code = "worker_error"
        job.error_message = "transient"
        job.next_attempt_at = utcnow()
        db.commit()

        service = IngestionService(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        retried = service.retry_job(str(job_id), "Token test-token")
        assert retried.state == "UPLOADING"
    finally:
        db.close()


def test_retry_job_missing_spool_does_not_mutate(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    from atlasdocs.services.documents import ValidationError

    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        job = db.get(IngestionJob, job_id)
        assert job is not None
        job.state = IngestionJobState.retryable_failure
        job.paperless_task_id = None
        job.error_code = "worker_error"
        db.commit()
        spool_path_for(job_id).unlink(missing_ok=True)
        old_cipher = job.token_ciphertext

        service = IngestionService(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        with pytest.raises(ValidationError, match="spool"):
            service.retry_job(str(job_id), "Token test-token")
        db.refresh(job)
        assert job.state == IngestionJobState.retryable_failure
        assert job.token_ciphertext == old_cipher
        assert job.error_code == "worker_error"
    finally:
        db.close()


def test_retryable_failure_expires_to_terminal(
    client: TestClient, paperless_transport: FakePaperlessTransport, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INGEST_RETRYABLE_RETENTION_SECONDS", "1")
    get_settings.cache_clear()
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        job = db.get(IngestionJob, job_id)
        assert job is not None
        job.state = IngestionJobState.retryable_failure
        job.error_code = "missing_document"
        job.updated_at = utcnow() - timedelta(seconds=30)
        db.commit()
        assert spool_path_for(job_id).exists()

        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.failed
        assert job.error_code == "retryable_expired"
        assert job.token_ciphertext is None
        assert not spool_path_for(job_id).exists()
    finally:
        db.close()
        get_settings.cache_clear()


def test_complete_with_document_unavailable_stays_retryable(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        paperless_transport.omit_related_document_on_success = True
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.resolving_document

        upload = paperless_transport.uploaded_files[-1]
        doc_id = upload["document_id"]
        paperless_transport.tasks[job.paperless_task_id]["related_document_ids"] = [doc_id]
        paperless_transport.tasks[job.paperless_task_id]["result_data"] = {"document_id": doc_id}
        paperless_transport.server_error.add(doc_id)
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        job.locked_by = None
        db.commit()

        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.resolving_document
        assert job.token_ciphertext is not None
        assert spool_path_for(job_id).exists()
    finally:
        db.close()


def test_resolution_unavailable_does_not_increment_attempt_count(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        paperless_transport.omit_related_document_on_success = True
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.resolving_document
        before = job.resolution_attempt_count

        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        job.locked_by = None
        db.commit()
        with patch.object(worker._paperless, "get_task", side_effect=PaperlessUnavailableError("down")):
            assert worker.run_once() is True
        db.refresh(job)
        assert job.resolution_attempt_count == before
        assert job.state == IngestionJobState.resolving_document
    finally:
        db.close()


def test_token_redaction_on_exception_path(
    client: TestClient, paperless_transport: FakePaperlessTransport, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "Token secret-abc"
    _connect(client, token=secret.removeprefix("Token "))
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        job = db.get(IngestionJob, job_id)
        assert job is not None
        worker = _worker(db, paperless_transport)
        with caplog.at_level(logging.INFO, logger="atlasdocs.services.ingest"):
            with patch.object(
                worker._paperless,
                "post_document",
                side_effect=RuntimeError(f"upstream rejected {secret}"),
            ):
                assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.failed
        assert job.error_message is not None
        assert "secret-abc" not in (job.error_message or "")
        assert secret not in (job.error_message or "")
        assert "secret-abc" not in caplog.text
    finally:
        db.close()


def test_no_raw_response_body_in_error_message(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.task_auto_succeed = False
    _connect(client)
    job_id = _enqueue(client)
    db = get_session_factory()()
    try:
        worker = _worker(db, paperless_transport)
        assert worker.run_once() is True
        job = db.get(IngestionJob, job_id)
        assert job is not None
        long_body = "X" * 2000
        paperless_transport.tasks[job.paperless_task_id]["status"] = "FAILURE"
        paperless_transport.tasks[job.paperless_task_id]["result"] = long_body
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        job.locked_by = None
        db.commit()

        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.failed
        assert job.error_message == "Paperless task failed"
        assert long_body not in (job.error_message or "")
    finally:
        db.close()
