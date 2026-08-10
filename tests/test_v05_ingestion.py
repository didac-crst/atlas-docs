"""v0.5 ingestion, login, encryption, bulk, and recovery tests."""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from atlasdocs.config import get_settings
from atlasdocs.db.models import IngestionJob, IngestionJobState, as_aware, utcnow
from atlasdocs.db.session import get_session_factory
from atlasdocs.security.tokens import decrypt_token, encrypt_token, token_fingerprint
from atlasdocs.services.ingest import IngestionWorker, spool_path_for
from atlasdocs.services.login_rate_limit import login_rate_limiter
from atlasdocs.services.paperless import PaperlessClient
from tests.conftest import AUTH
from tests.fakes import FakePaperlessTransport


def _connect(client: TestClient, token: str = "test-token") -> str:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    response = client.post(
        "/ui/api/connect",
        json={"csrf_token": csrf, "paperless_token": token},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_token_encryption_round_trip() -> None:
    key = "unit-test-encryption-key"
    cipher = encrypt_token("Token secret-value", key=key)
    assert "secret-value" not in cipher
    assert decrypt_token(cipher, key=key) == "Token secret-value"
    assert token_fingerprint("Token a") == token_fingerprint("Token a")
    assert token_fingerprint("Token a") != token_fingerprint("Token b")


def test_login_success_never_returns_token(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    paperless_transport.next_token = "must-not-leak"
    response = client.post(
        "/ui/api/login",
        json={"username": "ada", "password": "correct-horse", "csrf_token": csrf},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    text = response.text
    assert "must-not-leak" not in text
    assert "correct-horse" not in text
    assert "Token " not in text


def test_login_failure_generic_and_rate_limit(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("LOGIN_RATE_LIMIT_ATTEMPTS", "3")
    get_settings.cache_clear()
    login_rate_limiter.clear()
    for _ in range(3):
        csrf = client.get("/ui/api/session").json()["csrf_token"]
        response = client.post(
            "/ui/api/login",
            json={"username": "ada", "password": "wrong", "csrf_token": csrf},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication failed"
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    blocked = client.post(
        "/ui/api/login",
        json={"username": "ada", "password": "wrong", "csrf_token": csrf},
    )
    assert blocked.status_code == 429


def test_ingest_worker_ready_wipes_ciphertext(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    upload = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("note.pdf", b"%PDF-hello", "application/pdf")},
    )
    assert upload.status_code == 202
    job_id = upload.json()["id"]
    assert upload.json()["state"] == "UPLOADING"

    db = get_session_factory()()
    try:
        job = db.get(IngestionJob, uuid.UUID(job_id))
        assert job is not None
        assert job.token_ciphertext
        worker = IngestionWorker(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.ready
        assert job.token_ciphertext is None
        assert job.paperless_document_id is not None
        assert not spool_path_for(job.id).exists()
    finally:
        db.close()

    status = client.get(f"/ui/api/ingest/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["state"] == "READY"
    assert "Token" not in status.text


def test_ingest_duplicate_checksum_409(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    payload = b"identical-bytes"
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    first = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("a.pdf", payload, "application/pdf")},
    )
    assert first.status_code == 202
    job_id = first.json()["id"]
    db = get_session_factory()()
    try:
        worker = IngestionWorker(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        worker.run_once()
    finally:
        db.close()

    csrf = client.get("/ui/api/session").json()["csrf_token"]
    second = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("b.pdf", payload, "application/pdf")},
    )
    assert second.status_code == 409
    assert "paperless_document_id=" in second.json()["detail"]


def test_paperless_duplicate_fails_job(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    paperless_transport.post_document_duplicate = True
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    upload = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("dup.pdf", b"dup-content", "application/pdf")},
    )
    job_id = upload.json()["id"]
    db = get_session_factory()()
    try:
        worker = IngestionWorker(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        worker.run_once()
        job = db.get(IngestionJob, uuid.UUID(job_id))
        assert job is not None
        assert job.state == IngestionJobState.failed
        assert job.error_code == "duplicate"
        assert job.token_ciphertext is None
    finally:
        db.close()


def test_upload_size_limit(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("INGEST_MAX_UPLOAD_BYTES", "16")
    get_settings.cache_clear()
    _connect(client)
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    response = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("big.bin", b"x" * 64, "application/octet-stream")},
    )
    assert response.status_code == 422


def test_job_lease_reclaim_after_stale_lock(
    client: TestClient, paperless_transport: FakePaperlessTransport, monkeypatch
) -> None:
    monkeypatch.setenv("INGEST_LEASE_SECONDS", "1")
    get_settings.cache_clear()
    _connect(client)
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    upload = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("lease.pdf", b"lease-bytes", "application/pdf")},
    )
    job_id = uuid.UUID(upload.json()["id"])
    db = get_session_factory()()
    try:
        job = db.get(IngestionJob, job_id)
        assert job is not None
        job.locked_at = utcnow() - timedelta(seconds=30)
        job.locked_by = "dead-worker"
        db.commit()
        worker = IngestionWorker(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
            worker_id="reclaimer",
        )
        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.ready
    finally:
        db.close()


def test_bulk_relationships_per_doc_authz(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.denied.add(999)
    paperless_transport.documents[999] = {"id": 999, "title": "Secret"}
    response = client.post(
        "/documents/bulk-relationships",
        headers=AUTH,
        json={
            "paperless_document_ids": [184, 999],
            "relationship": "source-country",
            "target": "germany",
        },
    )
    assert response.status_code == 200
    results = {item["paperless_document_id"]: item for item in response.json()["results"]}
    assert results[184]["status"] == "created"
    assert results[999]["status"] == "forbidden_or_missing"
    assert "title" not in results[999]
    assert "Secret" not in response.text


def test_documents_search_filter(client: TestClient) -> None:
    response = client.get(
        "/documents",
        headers=AUTH,
        params={"classification": "any", "q": "Payslip", "sort": "title", "order": "asc"},
    )
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert titles
    assert all("Payslip" in (t or "") for t in titles)


def test_json_ingest_and_secret_leak_guards(client: TestClient) -> None:
    secret = "json-api-token-secret"
    response = client.post(
        "/ingest",
        headers={"Authorization": f"Token {secret}"},
        files={"document": ("api.pdf", b"api-bytes", "application/pdf")},
    )
    assert response.status_code == 202
    assert secret not in response.text
    assert "Token " not in response.text


def test_logout_keeps_inflight_job_token_until_terminal(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.task_auto_succeed = False
    csrf = _connect(client)
    upload = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("late.pdf", b"late-bytes", "application/pdf")},
    )
    job_id = uuid.UUID(upload.json()["id"])
    db = get_session_factory()()
    try:
        worker = IngestionWorker(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        worker.run_once()  # forward to PROCESSING
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionJobState.processing
        assert job.token_ciphertext
        assert spool_path_for(job_id).exists()
        cipher = job.token_ciphertext
    finally:
        db.close()

    csrf = client.get("/ui/api/session").json()["csrf_token"]
    client.post("/ui/api/disconnect", json={"csrf_token": csrf}, headers={"X-CSRF-Token": csrf})

    db = get_session_factory()()
    try:
        job = db.get(IngestionJob, job_id)
        assert job is not None
        assert job.token_ciphertext == cipher
        # Complete task and make the job claimable immediately.
        paperless_transport.tasks[job.paperless_task_id]["status"] = "SUCCESS"
        paperless_transport.tasks[job.paperless_task_id]["related_document"] = 777
        paperless_transport.documents[777] = {"id": 777, "title": "late"}
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        db.commit()
        worker = IngestionWorker(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.ready
        assert job.token_ciphertext is None
    finally:
        db.close()


def test_processing_timeout_ignores_queue_delay(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.task_auto_succeed = False
    csrf = _connect(client)
    upload = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("slow.pdf", b"slow-bytes", "application/pdf")},
    )
    assert upload.status_code == 202
    job_id = uuid.UUID(upload.json()["id"])

    db = get_session_factory()()
    try:
        job = db.get(IngestionJob, job_id)
        assert job is not None
        # Age the queued job before Paperless acceptance.
        queued_created_at = utcnow() - timedelta(hours=5)
        job.created_at = queued_created_at
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        db.commit()

        worker = IngestionWorker(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.processing
        assert job.processing_started_at is not None
        assert as_aware(job.processing_started_at) > as_aware(queued_created_at)
        assert as_aware(job.created_at) == as_aware(queued_created_at)
        started = job.processing_started_at

        # Polling must not extend the processing deadline.
        job.updated_at = utcnow()
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        db.commit()
        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.processing
        assert job.processing_started_at == started

        # Deadline is anchored to processing_started_at, not created_at/updated_at.
        job.processing_started_at = utcnow() - timedelta(
            seconds=get_settings().ingest_processing_timeout_seconds + 5
        )
        job.updated_at = utcnow()
        job.next_attempt_at = utcnow() - timedelta(seconds=1)
        job.locked_at = None
        db.commit()
        assert worker.run_once() is True
        db.refresh(job)
        assert job.state == IngestionJobState.failed
        assert job.error_code == "processing_timeout"
    finally:
        db.close()


def test_clear_completed_ingest_jobs_is_token_scoped(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client, token="owner-token")
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    upload = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("keep.pdf", b"%PDF-owner", "application/pdf")},
    )
    assert upload.status_code == 202
    owner_job_id = upload.json()["id"]

    db = get_session_factory()()
    try:
        worker = IngestionWorker(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        assert worker.run_once() is True
        owner_job = db.get(IngestionJob, uuid.UUID(owner_job_id))
        assert owner_job is not None
        assert owner_job.state == IngestionJobState.ready
        paperless_doc_id = owner_job.paperless_document_id

        other = IngestionJob(
            id=uuid.uuid4(),
            state=IngestionJobState.ready,
            original_filename="other.pdf",
            content_sha256="a" * 64,
            content_size_bytes=12,
            token_fingerprint=token_fingerprint("Token stranger"),
            paperless_document_id=999001,
        )
        db.add(other)
        db.commit()
        other_id = other.id
    finally:
        db.close()

    csrf = client.get("/ui/api/session").json()["csrf_token"]
    cleared = client.post(
        "/ui/api/ingest/jobs/clear-completed",
        headers={"X-CSRF-Token": csrf},
    )
    assert cleared.status_code == 200
    assert cleared.json()["cleared"] == 1

    listed = client.get("/ui/api/ingest/jobs")
    assert listed.status_code == 200
    assert listed.json()["items"] == []

    db = get_session_factory()()
    try:
        assert db.get(IngestionJob, uuid.UUID(owner_job_id)) is None
        assert db.get(IngestionJob, other_id) is not None
        # Clearing history must not delete the Paperless document id we recorded.
        assert paperless_doc_id is not None
        assert paperless_doc_id in paperless_transport.documents
    finally:
        db.close()
