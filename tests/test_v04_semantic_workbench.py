"""v0.4 entity API, reconciliation, and workbench coverage."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from atlasdocs.db.models import EXTERNAL_SYSTEM_PAPERLESS, Entity, EntityType, ExternalReference
from atlasdocs.db.session import get_session_factory
AUTH = {"Authorization": "Token test-token"}


def test_entity_api_document_to_person_and_organization(client: TestClient) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "germany"},
    )
    assert created.status_code == 201
    entity_id = created.json()["entity_id"]
    assert entity_id

    person = client.post(
        f"/entities/{entity_id}/relationships",
        headers=AUTH,
        json={"relationship": "concerns-person", "target": "alice"},
    )
    assert person.status_code == 201
    types = {item["type"] for item in person.json()["relationships"]}
    assert "concerns-person" in types
    assert "source-country" in types

    org = client.post(
        f"/entities/{entity_id}/relationships",
        headers=AUTH,
        json={
            "relationship": "issued-by",
            "target": "acme",
            "origin": "manual",
            "status": "confirmed",
        },
    )
    assert org.status_code == 201
    issued = [r for r in org.json()["relationships"] if r["type"] == "issued-by"][0]
    assert issued["target"] == "Acme"
    assert issued["origin"] == "manual"
    assert issued["status"] == "confirmed"
    assert issued["target_entity_id"]

    listed = client.get(f"/entities/{entity_id}/relationships", headers=AUTH)
    assert listed.status_code == 200
    assert len(listed.json()) >= 3


def test_entity_document_to_document_inverse(client: TestClient) -> None:
    source = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "document-type", "target": "payslip"},
    ).json()["entity_id"]

    created = client.post(
        f"/entities/{source}/relationships",
        headers=AUTH,
        json={"relationship": "derived-from", "target_paperless_id": 185},
    )
    assert created.status_code == 201
    assert any(r["type"] == "derived-from" for r in created.json()["relationships"])

    target_doc = client.get("/documents/185", headers=AUTH)
    assert target_doc.status_code == 200
    assert any(r["type"] == "has-derivative" for r in target_doc.json()["relationships"])

    duplicate = client.post(
        f"/entities/{source}/relationships",
        headers=AUTH,
        json={"relationship": "derived-from", "target_paperless_id": 185},
    )
    assert duplicate.status_code == 409


def test_entity_authz_denial_hides_semantics(
    client: TestClient, paperless_transport
) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "germany"},
    )
    entity_id = created.json()["entity_id"]
    paperless_transport.denied.add(184)
    denied = client.get(f"/entities/{entity_id}", headers=AUTH)
    assert denied.status_code == 404
    assert "Germany" not in denied.text


def test_reconcile_idempotent_and_reports_missing_inaccessible(
    client: TestClient, paperless_transport
) -> None:
    session = get_session_factory()()
    try:
        entity = Entity(entity_type=EntityType.document)
        session.add(entity)
        session.flush()
        session.add(
            ExternalReference(
                entity_id=entity.id,
                system=EXTERNAL_SYSTEM_PAPERLESS,
                external_id="999",
            )
        )
        denied_entity = Entity(entity_type=EntityType.document)
        session.add(denied_entity)
        session.flush()
        session.add(
            ExternalReference(
                entity_id=denied_entity.id,
                system=EXTERNAL_SYSTEM_PAPERLESS,
                external_id="186",
            )
        )
        session.commit()
    finally:
        session.close()

    paperless_transport.denied.add(186)

    first = client.post("/reconcile", headers=AUTH, json={"dry_run": False, "limit": 10})
    assert first.status_code == 200
    body = first.json()
    assert body["paperless_documents_seen"] >= 2
    assert 184 in body["created"] or 184 in body["already_present"]
    assert 999 in body["missing_in_paperless"]
    assert 186 in body["inaccessible_in_paperless"]
    assert "not deleted" in body["human_summary"].lower()

    second = client.post("/reconcile", headers=AUTH, json={"dry_run": False})
    assert second.status_code == 200
    assert second.json()["created"].count(184) == 0
    assert 184 in second.json()["already_present"]

    session = get_session_factory()()
    try:
        refs = list(
            session.scalars(
                select(ExternalReference).where(
                    ExternalReference.system == EXTERNAL_SYSTEM_PAPERLESS,
                    ExternalReference.external_id == "999",
                )
            )
        )
        assert len(refs) == 1
    finally:
        session.close()


def test_reconcile_dry_run_does_not_write(client: TestClient) -> None:
    dry = client.post("/reconcile", headers=AUTH, json={"dry_run": True, "limit": 5})
    assert dry.status_code == 200
    assert dry.json()["dry_run"] is True
    would_create = set(dry.json()["created"])
    session = get_session_factory()()
    try:
        for paperless_id in would_create:
            assert (
                session.scalar(
                    select(ExternalReference).where(
                        ExternalReference.system == EXTERNAL_SYSTEM_PAPERLESS,
                        ExternalReference.external_id == str(paperless_id),
                    )
                )
                is None
            )
    finally:
        session.close()


def test_reconcile_service_pagination(
    client: TestClient, paperless_transport
) -> None:
    for doc_id in range(200, 230):
        paperless_transport.documents[doc_id] = {"id": doc_id, "title": f"Doc {doc_id}"}
    limited = client.post("/reconcile", headers=AUTH, json={"dry_run": True, "limit": 3})
    assert limited.status_code == 200
    assert limited.json()["paperless_documents_seen"] == 3


def test_ui_shows_paperless_metadata_and_reconcile(client: TestClient) -> None:
    connect = client.get("/ui/connect")
    csrf = connect.text.split('name="csrf_token" value="')[1].split('"')[0]
    client.post(
        "/ui/connect",
        data={"csrf_token": csrf, "paperless_token": "test-token"},
        follow_redirects=False,
    )
    detail = client.get("/ui/documents/184")
    assert detail.status_code == 200
    assert "Acme Payroll" in detail.text
    assert "2024-01-15" in detail.text
    assert "Payslip" in detail.text

    reconcile = client.get("/ui/reconcile")
    assert reconcile.status_code == 200
    assert "never deleted" in reconcile.text.lower()
    csrf = reconcile.text.split('name="csrf_token" value="')[1].split('"')[0]
    ran = client.post(
        "/ui/reconcile",
        data={"csrf_token": csrf, "dry_run": "1", "limit": "2"},
    )
    assert ran.status_code == 200
    assert "Dry-run complete" in ran.text


def test_ui_reconcile_csrf_required(client: TestClient) -> None:
    connect = client.get("/ui/connect")
    csrf = connect.text.split('name="csrf_token" value="')[1].split('"')[0]
    client.post(
        "/ui/connect",
        data={"csrf_token": csrf, "paperless_token": "test-token"},
        follow_redirects=False,
    )
    bad = client.post("/ui/reconcile", data={"csrf_token": "nope", "dry_run": "1"})
    assert bad.status_code == 400
    assert "Invalid CSRF token" in bad.text
