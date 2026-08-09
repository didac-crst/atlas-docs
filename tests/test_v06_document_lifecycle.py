"""v0.6 document delete / replace lifecycle tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from atlasdocs.db.models import DocumentReplacementHistory, Entity
from atlasdocs.db.session import get_session_factory
from atlasdocs.services.ingest import IngestionWorker
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


def _ensure_entity(client: TestClient, paperless_id: int = 184) -> str:
    created = client.post(
        f"/documents/{paperless_id}/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "germany"},
    )
    assert created.status_code == 201
    entity_id = created.json()["entity_id"]
    assert entity_id
    return entity_id


def _run_worker(paperless_transport: FakePaperlessTransport) -> None:
    db = get_session_factory()()
    try:
        worker = IngestionWorker(
            db,
            PaperlessClient(base_url="http://paperless.test", transport=paperless_transport),
        )
        while worker.run_once():
            pass
    finally:
        db.close()


def test_delete_requires_confirmation(client: TestClient) -> None:
    _ensure_entity(client)
    denied = client.request(
        "DELETE",
        "/documents/184",
        headers=AUTH,
        json={"confirm": False},
    )
    assert denied.status_code == 422
    still = client.get("/documents/184", headers=AUTH)
    assert still.status_code == 200


def test_delete_authorization_denied(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _ensure_entity(client)
    paperless_transport.delete_denied.add(184)
    response = client.request(
        "DELETE",
        "/documents/184",
        headers=AUTH,
        json={"confirm": True},
    )
    # Forbidden is mapped to 404 so existence is not leaked.
    assert response.status_code == 404
    assert 184 in paperless_transport.documents
    assert 184 not in paperless_transport.deleted_document_ids


def test_ui_delete_requires_csrf(client: TestClient) -> None:
    _connect(client)
    _ensure_entity(client)
    response = client.request(
        "DELETE",
        "/ui/api/documents/184",
        json={"confirm": True},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid CSRF token"


def test_delete_tombstones_and_hides_from_queries(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    csrf = _connect(client)
    entity_id = _ensure_entity(client)

    deleted = client.request(
        "DELETE",
        "/ui/api/documents/184",
        headers={"X-CSRF-Token": csrf},
        json={"confirm": True},
    )
    assert deleted.status_code == 204
    assert 184 in paperless_transport.deleted_document_ids
    assert "Token " not in (deleted.text or "")

    assert client.get("/documents/184", headers=AUTH).status_code == 404
    assert client.get(f"/entities/{entity_id}", headers=AUTH).status_code == 404
    assert client.get("/ui/api/documents/184/preview").status_code == 404
    assert client.get("/ui/api/documents/184/download").status_code == 404

    db = get_session_factory()()
    try:
        entity = db.get(Entity, uuid.UUID(entity_id))
        assert entity is not None
        assert entity.deleted_at is not None
        assert entity.semantic_completeness == "partial"
    finally:
        db.close()


def test_replace_preserves_uuid_relationships_and_history(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    csrf = _connect(client)
    entity_id = _ensure_entity(client)
    rels_before = client.get("/documents/184", headers=AUTH).json()["relationships"]
    assert any(item["type"] == "source-country" for item in rels_before)

    csrf = client.get("/ui/api/session").json()["csrf_token"]
    replace = client.post(
        "/ui/api/documents/184/replace",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("fixed.pdf", b"%PDF-replacement", "application/pdf")},
        data={"reason": "better scan"},
    )
    assert replace.status_code == 202
    job_id = replace.json()["id"]
    assert "Token " not in replace.text

    _run_worker(paperless_transport)
    job = client.get(f"/ui/api/ingest/jobs/{job_id}").json()
    assert job["state"] == "READY"
    new_id = job["paperless_document_id"]
    assert new_id is not None
    assert new_id != 184
    assert 184 in paperless_transport.deleted_document_ids
    assert new_id in paperless_transport.documents
    assert 184 not in paperless_transport.documents

    after = client.get(f"/documents/{new_id}", headers=AUTH)
    assert after.status_code == 200
    body = after.json()
    assert body["entity_id"] == entity_id
    assert any(item["type"] == "source-country" for item in body["relationships"])
    assert client.get("/documents/184", headers=AUTH).status_code == 404

    db = get_session_factory()()
    try:
        history = list(
            db.scalars(
                select(DocumentReplacementHistory).where(
                    DocumentReplacementHistory.entity_id == uuid.UUID(entity_id)
                )
            )
        )
        assert len(history) == 1
        assert history[0].previous_external_id == "184"
        assert history[0].new_external_id == str(new_id)
        assert history[0].reason == "better scan"
        assert history[0].new_checksum
    finally:
        db.close()


def test_failed_replace_keeps_old_paperless_document(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    csrf = _connect(client)
    entity_id = _ensure_entity(client)
    paperless_transport.post_document_server_error = True
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    replace = client.post(
        "/ui/api/documents/184/replace",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("bad.pdf", b"%PDF-bad", "application/pdf")},
    )
    assert replace.status_code == 202
    job_id = replace.json()["id"]
    _run_worker(paperless_transport)

    job = client.get(f"/ui/api/ingest/jobs/{job_id}").json()
    assert job["state"] == "UPLOADING"
    assert 184 in paperless_transport.documents
    assert 184 not in paperless_transport.deleted_document_ids
    still = client.get("/documents/184", headers=AUTH)
    assert still.status_code == 200
    assert still.json()["entity_id"] == entity_id


def test_replace_retries_old_paperless_delete_after_switch(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    csrf = _connect(client)
    entity_id = _ensure_entity(client)
    paperless_transport.delete_server_error.add(184)

    csrf = client.get("/ui/api/session").json()["csrf_token"]
    replace = client.post(
        "/ui/api/documents/184/replace",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("retry-delete.pdf", b"%PDF-retry-delete", "application/pdf")},
        data={"reason": "retry cleanup"},
    )
    assert replace.status_code == 202
    job_id = replace.json()["id"]
    _run_worker(paperless_transport)

    mid = client.get(f"/ui/api/ingest/jobs/{job_id}").json()
    assert mid["state"] != "READY"
    upload = paperless_transport.uploaded_files[-1]
    new_id = upload["document_id"]
    switched = client.get(f"/documents/{new_id}", headers=AUTH)
    assert switched.status_code == 200
    assert switched.json()["entity_id"] == entity_id
    assert 184 not in paperless_transport.deleted_document_ids

    paperless_transport.delete_server_error.discard(184)
    db = get_session_factory()()
    try:
        from atlasdocs.db.models import IngestionJob, utcnow

        job_row = db.get(IngestionJob, uuid.UUID(job_id))
        assert job_row is not None
        job_row.next_attempt_at = utcnow()
        job_row.locked_at = None
        job_row.locked_by = None
        db.commit()
    finally:
        db.close()

    _run_worker(paperless_transport)
    finished = client.get(f"/ui/api/ingest/jobs/{job_id}").json()
    assert finished["state"] == "READY"
    assert finished["paperless_document_id"] == new_id
    assert 184 in paperless_transport.deleted_document_ids
    assert 184 not in paperless_transport.documents


def test_new_ingest_creates_new_entity(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    first = _ensure_entity(client)
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    upload = client.post(
        "/ui/api/ingest",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("other.pdf", b"%PDF-other-doc", "application/pdf")},
    )
    assert upload.status_code == 202
    job_id = upload.json()["id"]
    _run_worker(paperless_transport)
    job = client.get(f"/ui/api/ingest/jobs/{job_id}").json()
    assert job["state"] == "READY"
    second = client.get(f"/documents/{job['paperless_document_id']}", headers=AUTH).json()
    assert second["entity_id"] != first


def test_completeness_recalculated_on_relationship_remove_and_delete(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    csrf = _connect(client)
    entity_id = _ensure_entity(client)
    detail = client.get("/documents/184", headers=AUTH).json()
    assert detail["semantic_completeness"] != "empty"
    rel_id = detail["relationships"][0]["id"]

    csrf = client.get("/ui/api/session").json()["csrf_token"]
    removed = client.delete(
        f"/ui/api/relationships/{rel_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert removed.status_code == 204
    after_remove = client.get("/documents/184", headers=AUTH).json()
    assert after_remove["semantic_completeness"] == "empty"

    csrf = client.get("/ui/api/session").json()["csrf_token"]
    client.request(
        "DELETE",
        "/ui/api/documents/184",
        headers={"X-CSRF-Token": csrf},
        json={"confirm": True},
    )
    db = get_session_factory()()
    try:
        entity = db.get(Entity, uuid.UUID(entity_id))
        assert entity is not None
        assert entity.deleted_at is not None
        assert entity.semantic_completeness == "empty"
    finally:
        db.close()


def test_reconcile_skips_tombstoned_missing_refs(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    csrf = _connect(client)
    _ensure_entity(client)
    client.request(
        "DELETE",
        "/ui/api/documents/184",
        headers={"X-CSRF-Token": csrf},
        json={"confirm": True},
    )
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    result = client.post(
        "/ui/api/reconcile",
        headers={"X-CSRF-Token": csrf},
        json={"dry_run": True},
    )
    assert result.status_code == 200
    body = result.json()
    assert 184 not in body["missing_in_paperless"]
    assert "Token " not in result.text


def test_external_ref_switches_only_after_validation(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    csrf = _connect(client)
    entity_id = _ensure_entity(client)

    paperless_transport.task_auto_succeed = False
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    replace = client.post(
        "/ui/api/documents/184/replace",
        headers={"X-CSRF-Token": csrf},
        files={"document": ("pending.pdf", b"%PDF-pending", "application/pdf")},
    )
    assert replace.status_code == 202
    job_id = replace.json()["id"]
    _run_worker(paperless_transport)

    job = client.get(f"/ui/api/ingest/jobs/{job_id}").json()
    assert job["state"] != "READY"
    mid = client.get("/documents/184", headers=AUTH).json()
    assert mid["entity_id"] == entity_id
    assert 184 in paperless_transport.documents

    upload = paperless_transport.uploaded_files[-1]
    task_id = upload["task_id"]
    doc_id = upload["document_id"]
    paperless_transport.tasks[task_id] = {
        "task_id": task_id,
        "status": "SUCCESS",
        "related_document": doc_id,
        "result": str(doc_id),
    }
    paperless_transport.documents[doc_id] = {
        "id": doc_id,
        "title": "pending.pdf",
        "created_date": "2024-06-01",
    }
    paperless_transport.task_auto_succeed = True

    db = get_session_factory()()
    try:
        from atlasdocs.db.models import IngestionJob, utcnow

        job_row = db.get(IngestionJob, uuid.UUID(job_id))
        assert job_row is not None
        job_row.next_attempt_at = utcnow()
        job_row.locked_at = None
        job_row.locked_by = None
        db.commit()
    finally:
        db.close()

    _run_worker(paperless_transport)

    finished = client.get(f"/ui/api/ingest/jobs/{job_id}").json()
    assert finished["state"] == "READY"
    assert finished["paperless_document_id"] == doc_id
    assert client.get("/documents/184", headers=AUTH).status_code == 404
    assert client.get(f"/documents/{doc_id}", headers=AUTH).json()["entity_id"] == entity_id
