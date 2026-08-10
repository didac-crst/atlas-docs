from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from atlasdocs.db.models import (
    EXTERNAL_SYSTEM_PAPERLESS,
    Base,
    Concept,
    ExternalReference,
    Relationship,
    RelationshipType,
)
from atlasdocs.db.seed import seed_from_path
from atlasdocs.db.session import get_engine, get_session_factory, reset_engine
from atlasdocs.db.session import get_session_factory
from atlasdocs.ui.sessions import DbSessionStore
AUTH = {"Authorization": "Token test-token"}
SEED_PATH = Path(__file__).resolve().parents[1] / "config" / "seed" / "v0.1.yaml"


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_redirects_to_ui(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ui"


def test_authorization_required(client: TestClient) -> None:
    assert client.get("/documents/184").status_code == 401
    assert (
        client.post(
            "/documents/184/relationships",
            json={"relationship": "source-country", "target": "Germany"},
        ).status_code
        == 401
    )


def test_seed_loads_ontologies_and_relationship_types(client: TestClient) -> None:
    session = get_session_factory()()
    try:
        concepts = {c.name for c in session.scalars(select(Concept))}
        assert concepts == {
            "France",
            "Germany",
            "Spain",
            "Payslip",
            "Invoice",
            "Alice",
            "Bob",
            "Acme",
            "Contoso",
            "Sample Case",
        }
        types = {t.code for t in session.scalars(select(RelationshipType))}
        assert types == {
            "source-country",
            "document-type",
            "concerns",
            "issued-by",
            "concerns-person",
            "belongs-to",
            "related-to",
            "derived-from",
            "has-derivative",
            "replies-to",
            "answered-by",
        }
        for concept in session.scalars(select(Concept)):
            assert concept.entity is not None
            assert concept.entity.entity_type.value == "concept"
            assert concept.entity.id == concept.id
    finally:
        session.close()


def test_seed_is_idempotent(tmp_path: Path) -> None:
    reset_engine()
    engine = get_engine(f"sqlite+pysqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)
    session = get_session_factory()()
    try:
        seed_from_path(session, SEED_PATH)
        seed_from_path(session, SEED_PATH)
        session.commit()
        assert len(list(session.scalars(select(Concept)))) == 10
        assert len(list(session.scalars(select(RelationshipType)))) == 11
    finally:
        session.close()
        reset_engine()


def test_create_and_get_relationship(client: TestClient) -> None:
    create = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["paperless_document_id"] == 184
    assert body["title"] == "Payslip Germany"
    assert body["open_url"] == "http://paperless.example.test/documents/184/"
    assert "Token" not in body["open_url"]
    assert len(body["relationships"]) == 1
    assert body["relationships"][0]["type"] == "source-country"
    assert body["relationships"][0]["target"] == "Germany"
    assert body["relationships"][0]["origin"] == "manual"
    assert body["relationships"][0]["status"] == "confirmed"
    assert body["relationships"][0]["id"]

    fetched = client.get("/documents/184", headers=AUTH)
    assert fetched.status_code == 200
    assert fetched.json()["relationships"] == body["relationships"]

    session = get_session_factory()()
    try:
        reference = session.scalar(
            select(ExternalReference).where(
                ExternalReference.system == EXTERNAL_SYSTEM_PAPERLESS,
                ExternalReference.external_id == "184",
            )
        )
        assert reference is not None
        assert str(reference.entity_id) != "184"
        assert reference.external_id == "184"
        assert reference.entity_id != reference.id
        assert body["entity_id"] == str(reference.entity_id)
    finally:
        session.close()


def test_missing_paperless_document(client: TestClient, paperless_transport: FakePaperlessTransport) -> None:
    response = client.post(
        "/documents/999/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    )
    assert response.status_code == 404
    session = get_session_factory()()
    try:
        assert (
            session.scalar(
                select(ExternalReference).where(
                    ExternalReference.system == EXTERNAL_SYSTEM_PAPERLESS,
                    ExternalReference.external_id == "999",
                )
            )
            is None
        )
    finally:
        session.close()
    assert 999 in paperless_transport.document_calls


def test_duplicate_relationship_rejected(client: TestClient) -> None:
    payload = {"relationship": "source-country", "target": "Germany"}
    assert client.post("/documents/184/relationships", headers=AUTH, json=payload).status_code == 201
    duplicate = client.post("/documents/184/relationships", headers=AUTH, json=payload)
    assert duplicate.status_code == 409


def test_invalid_target_rejected(client: TestClient) -> None:
    response = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Atlantis"},
    )
    assert response.status_code == 422


def test_invalid_relationship_type_rejected(client: TestClient) -> None:
    response = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "not-a-real-type", "target": "Germany"},
    )
    assert response.status_code == 422


def test_paperless_server_error(client: TestClient, paperless_transport: FakePaperlessTransport) -> None:
    paperless_transport.server_error.add(184)
    response = client.get("/documents/184", headers=AUTH)
    assert response.status_code == 502


def test_paperless_timeout(client: TestClient, paperless_transport: FakePaperlessTransport) -> None:
    paperless_transport.timeout.add(184)
    response = client.get("/documents/184", headers=AUTH)
    assert response.status_code == 502


def test_authorization_boundary_hides_document(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    assert (
        client.post(
            "/documents/184/relationships",
            headers=AUTH,
            json={"relationship": "document-type", "target": "Payslip"},
        ).status_code
        == 201
    )

    paperless_transport.denied.add(184)
    response = client.get("/documents/184", headers=AUTH)
    assert response.status_code == 404
    assert "relationships" not in response.json() or "detail" in response.json()


def test_paperless_client_uses_rest_only() -> None:
    source = Path(__file__).resolve().parents[1] / "src" / "atlasdocs" / "services" / "paperless.py"
    text = source.read_text(encoding="utf-8")
    assert "psycopg" not in text
    assert "sqlalchemy" not in text
    assert "/api/documents/" in text


def test_unclassified_list_paginated_without_n_plus_one(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    # Classify 186 so it is filtered out of the unclassified page.
    assert (
        client.post(
            "/documents/186/relationships",
            headers=AUTH,
            json={"relationship": "source-country", "target": "Germany"},
        ).status_code
        == 201
    )
    paperless_transport.document_calls.clear()
    paperless_transport.calls.clear()

    response = client.get("/documents?unclassified=true&page=1&page_size=25", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 25
    ids = {item["paperless_document_id"] for item in body["items"]}
    assert 184 in ids
    assert 185 in ids
    assert 186 not in ids
    list_calls = [
        call
        for call in paperless_transport.calls
        if call.startswith("GET /api/documents") and "page_size=25" in call
    ]
    assert len(list_calls) == 1
    assert paperless_transport.document_calls == []


def test_unclassified_fills_across_paperless_pages(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    # Make page-size-1 scans: first Paperless page is classified, second is not.
    paperless_transport.documents = {
        184: {"id": 184, "title": "Classified"},
        185: {"id": 185, "title": "Needs work"},
    }
    assert (
        client.post(
            "/documents/184/relationships",
            headers=AUTH,
            json={"relationship": "source-country", "target": "germany"},
        ).status_code
        == 201
    )
    paperless_transport.calls.clear()
    response = client.get("/documents?unclassified=true&page=1&page_size=1", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert [item["paperless_document_id"] for item in body["items"]] == [185]
    list_calls = [call for call in paperless_transport.calls if call.startswith("GET /api/documents")]
    assert len(list_calls) >= 2


def test_unclassified_empty_page(client: TestClient, paperless_transport: FakePaperlessTransport) -> None:
    for doc_id in list(paperless_transport.documents):
        assert (
            client.post(
                f"/documents/{doc_id}/relationships",
                headers=AUTH,
                json={"relationship": "source-country", "target": "Germany"},
            ).status_code
            == 201
        )
    response = client.get("/documents?unclassified=true", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_delete_relationship(client: TestClient) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    ).json()
    rel_id = created["relationships"][0]["id"]
    deleted = client.delete(f"/relationships/{rel_id}", headers=AUTH)
    assert deleted.status_code == 204
    fetched = client.get("/documents/184", headers=AUTH)
    assert fetched.json()["relationships"] == []


def test_relationship_types_and_concepts(client: TestClient) -> None:
    assert client.get("/relationship-types").status_code == 401
    assert client.get("/ontologies/country/concepts").status_code == 401
    types = client.get("/relationship-types", headers=AUTH)
    assert types.status_code == 200
    codes = {item["code"] for item in types.json()}
    assert codes == {
        "source-country",
        "document-type",
        "concerns",
        "issued-by",
        "concerns-person",
        "belongs-to",
        "related-to",
        "derived-from",
        "has-derivative",
        "replies-to",
        "answered-by",
    }
    by_code = {item["code"]: item for item in types.json()}
    assert by_code["related-to"]["directionality"] == "symmetric"
    assert by_code["replies-to"]["inverse"] == "answered-by"
    assert by_code["answered-by"]["inverse"] == "replies-to"
    assert by_code["source-country"]["target_entity_types"] == ["country"]
    assert by_code["replies-to"]["target_entity_types"] == ["document"]
    assert by_code["belongs-to"]["target_entity_types"] == ["case"]
    concepts = client.get("/ontologies/country/concepts", headers=AUTH)
    assert concepts.status_code == 200
    assert {item["name"] for item in concepts.json()} == {"France", "Germany", "Spain"}


def test_symmetric_relationship_creates_companion_edge(client: TestClient) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "related-to", "target": "Germany"},
    )
    assert created.status_code == 201
    assert len(created.json()["relationships"]) == 1
    assert created.json()["relationships"][0]["type"] == "related-to"

    session = get_session_factory()()
    try:
        edges = list(session.scalars(select(Relationship)))
        assert len(edges) == 2
        pairs = {(e.source_entity_id, e.target_entity_id) for e in edges}
        forward = next(iter(pairs))
        assert {(forward[1], forward[0])} == pairs - {forward}
    finally:
        session.close()


def test_inverse_relationship_materializes_companion(client: TestClient) -> None:
    source = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "document-type", "target": "payslip"},
    ).json()["entity_id"]
    created = client.post(
        f"/entities/{source}/relationships",
        headers=AUTH,
        json={"relationship": "replies-to", "target_paperless_id": 185},
    )
    assert created.status_code == 201
    assert any(rel["type"] == "replies-to" for rel in created.json()["relationships"])

    session = get_session_factory()()
    try:
        edges = list(
            session.scalars(
                select(Relationship).options(
                    joinedload(Relationship.relationship_type),
                )
            )
        )
        by_code = {e.relationship_type.code: e for e in edges}
        assert {"answered-by", "replies-to"} <= set(by_code)
        forward = by_code["replies-to"]
        inverse = by_code["answered-by"]
        assert inverse.source_entity_id == forward.target_entity_id
        assert inverse.target_entity_id == forward.source_entity_id
    finally:
        session.close()


def test_create_relationship_accepts_concept_code(client: TestClient) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "germany"},
    )
    assert created.status_code == 201
    assert created.json()["relationships"][0]["target"] == "Germany"


def test_get_document_with_multiple_relationships(client: TestClient) -> None:
    assert (
        client.post(
            "/documents/184/relationships",
            headers=AUTH,
            json={"relationship": "source-country", "target": "germany"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/documents/184/relationships",
            headers=AUTH,
            json={"relationship": "document-type", "target": "payslip"},
        ).status_code
        == 201
    )
    fetched = client.get("/documents/184", headers=AUTH)
    assert fetched.status_code == 200
    assert len(fetched.json()["relationships"]) == 2


def test_ui_requires_session_and_hides_token(client: TestClient) -> None:
    spa = client.get("/ui/")
    assert spa.status_code in {200, 503}
    session = client.get("/ui/api/session")
    assert session.status_code == 200
    body = session.json()
    assert body["authenticated"] is False
    assert body["csrf_token"]
    assert "Token " not in session.text
    assert "paperless" not in body


def test_session_cookie_is_opaque_and_excludes_paperless_token(client: TestClient) -> None:
    session = client.get("/ui/api/session").json()
    secret = "super-secret-paperless-token-value"
    connected = client.post(
        "/ui/api/connect",
        json={"csrf_token": session["csrf_token"], "paperless_token": secret},
    )
    assert connected.status_code == 200
    assert connected.json()["authenticated"] is True

    set_cookie = connected.headers.get("set-cookie", "")
    assert "atlasdocs_sid=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie or "SameSite=Lax" in set_cookie
    assert secret not in set_cookie
    assert "Token " not in set_cookie
    assert f"Token {secret}" not in set_cookie
    assert secret not in connected.text

    cookie_value = client.cookies.get("atlasdocs_sid")
    assert cookie_value
    assert secret not in cookie_value
    assert "Token" not in cookie_value

    db = get_session_factory()()
    try:
        stored = DbSessionStore(db).get(cookie_value)
        assert stored is not None
        assert stored.paperless_authorization == f"Token {secret}"
    finally:
        db.close()


def test_ui_logout_invalidates_server_session(client: TestClient) -> None:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    client.post(
        "/ui/api/connect",
        json={"csrf_token": csrf, "paperless_token": "test-token"},
    )
    sid = client.cookies.get("atlasdocs_sid")
    db = get_session_factory()()
    try:
        assert DbSessionStore(db).get(sid) is not None
    finally:
        db.close()

    csrf = client.get("/ui/api/session").json()["csrf_token"]
    disconnected = client.post(
        "/ui/api/disconnect",
        json={"csrf_token": csrf},
        headers={"X-CSRF-Token": csrf},
    )
    assert disconnected.status_code == 200
    assert disconnected.json()["authenticated"] is False
    db = get_session_factory()()
    try:
        assert DbSessionStore(db).get(sid) is None
    finally:
        db.close()
    assert client.get("/ui/api/documents").status_code == 401


def test_ui_classify_via_bff(client: TestClient) -> None:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    connected = client.post(
        "/ui/api/connect",
        json={"csrf_token": csrf, "paperless_token": "test-token"},
    )
    assert connected.status_code == 200
    csrf = connected.json()["csrf_token"]

    detail = client.get("/ui/api/documents/184")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Payslip Germany"
    assert "test-token" not in detail.text

    classified = client.post(
        "/ui/api/documents/184/relationships",
        headers={"X-CSRF-Token": csrf},
        json={"relationship": "source-country", "target": "Germany"},
    )
    assert classified.status_code == 201
    body = classified.json()
    assert any(item["type"] == "source-country" and item["target"] == "Germany" for item in body["relationships"])
    assert "test-token" not in classified.text
