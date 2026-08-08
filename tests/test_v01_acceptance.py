from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from atlasdocs.api import create_app
from atlasdocs.config import UNCLASSIFIED_PAGE_SIZE, get_settings
from atlasdocs.db.models import Base, Concept, DocumentReference, RelationshipType
from atlasdocs.db.seed import seed_from_path
from atlasdocs.db.session import get_db, get_engine, get_session_factory, reset_engine
from atlasdocs.services.paperless import PaperlessClient
from atlasdocs.ui.sessions import session_store

SEED_PATH = Path(__file__).resolve().parents[1] / "config" / "seed" / "v0.1.yaml"
AUTH = {"Authorization": "Token test-token"}


class FakePaperlessTransport(httpx.BaseTransport):
    """Deterministic Paperless REST stand-in. No real HTTP or Paperless DB."""

    def __init__(self) -> None:
        self.documents: dict[int, dict] = {
            184: {"id": 184, "title": "Payslip Germany"},
            185: {"id": 185, "title": "Invoice Spain"},
            186: {"id": 186, "title": "Already classified"},
        }
        self.denied: set[int] = set()
        self.unauthorized: set[int] = set()
        self.server_error: set[int] = set()
        self.timeout: set[int] = set()
        self.list_denied = False
        self.list_server_error = False
        self.calls: list[str] = []
        self.document_calls: list[int] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.rstrip("/")
        self.calls.append(f"{request.method} {request.url.path}?{request.url.query}")

        if path.endswith("/api/documents"):
            if self.list_server_error:
                return httpx.Response(503, json={"detail": "unavailable"})
            if self.list_denied:
                return httpx.Response(403, json={"detail": "forbidden"})
            query = parse_qs(urlparse(str(request.url)).query)
            page = int(query.get("page", ["1"])[0])
            page_size = int(query.get("page_size", [str(UNCLASSIFIED_PAGE_SIZE)])[0])
            ordered = sorted(self.documents.values(), key=lambda item: item["id"])
            start = (page - 1) * page_size
            chunk = ordered[start : start + page_size]
            return httpx.Response(
                200,
                json={
                    "count": len(ordered),
                    "next": "next" if start + page_size < len(ordered) else None,
                    "previous": "prev" if page > 1 else None,
                    "results": chunk,
                },
            )

        document_id = int(path.split("/")[-1])
        self.document_calls.append(document_id)
        if document_id in self.timeout:
            raise httpx.TimeoutException("timed out", request=request)
        if document_id in self.server_error:
            return httpx.Response(503, json={"detail": "unavailable"})
        if document_id in self.unauthorized:
            return httpx.Response(401, json={"detail": "unauthorized"})
        if document_id in self.denied:
            return httpx.Response(403, json={"detail": "forbidden"})
        if document_id not in self.documents:
            return httpx.Response(404, json={"detail": "not found"})
        return httpx.Response(200, json=self.documents[document_id])


@pytest.fixture()
def paperless_transport() -> FakePaperlessTransport:
    return FakePaperlessTransport()


@pytest.fixture()
def client(paperless_transport: FakePaperlessTransport, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("ATLASDOCS_ENV", "development")
    monkeypatch.setenv("SESSION_SECURE", "false")
    get_settings.cache_clear()
    session_store.clear()
    reset_engine()
    db_path = tmp_path / "atlasdocs.db"
    engine = get_engine(f"sqlite+pysqlite:///{db_path}")
    Base.metadata.create_all(engine)

    session = get_session_factory()()
    seed_from_path(session, SEED_PATH)
    session.commit()
    session.close()

    app = create_app()

    def override_db():
        session = get_session_factory()()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def override_paperless() -> PaperlessClient:
        return PaperlessClient(
            base_url="http://paperless.test",
            transport=paperless_transport,
        )

    from atlasdocs.api.routes import get_paperless_client

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_paperless_client] = override_paperless

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    session_store.clear()
    reset_engine()
    get_settings.cache_clear()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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
        assert concepts == {"France", "Germany", "Spain", "Payslip", "Invoice"}
        types = {t.code for t in session.scalars(select(RelationshipType))}
        assert types == {"source-country", "document-type", "concerns"}
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
        assert len(list(session.scalars(select(Concept)))) == 5
        assert len(list(session.scalars(select(RelationshipType)))) == 3
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
    assert body["open_url"].endswith("/documents/184/")
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
            select(DocumentReference).where(DocumentReference.paperless_document_id == 184)
        )
        assert reference is not None
        assert str(reference.entity_id) != "184"
        assert reference.paperless_document_id == 184
        assert reference.entity_id != reference.id
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
                select(DocumentReference).where(DocumentReference.paperless_document_id == 999)
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
    assert response.status_code == 400


def test_invalid_relationship_type_rejected(client: TestClient) -> None:
    response = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "issued-by", "target": "Germany"},
    )
    assert response.status_code == 400


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
    types = client.get("/relationship-types", headers=AUTH)
    assert types.status_code == 200
    codes = {item["code"] for item in types.json()}
    assert codes == {"source-country", "document-type", "concerns"}
    concepts = client.get("/ontologies/country/concepts", headers=AUTH)
    assert concepts.status_code == 200
    assert {item["name"] for item in concepts.json()} == {"France", "Germany", "Spain"}


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
    assert client.get("/ui", follow_redirects=False).status_code == 303
    connect = client.get("/ui/connect")
    assert connect.status_code == 200
    assert "paperless_token" in connect.text
    assert "test-token" not in connect.text
    assert "Token " not in connect.text or "Paperless token" in connect.text


def test_session_cookie_is_opaque_and_excludes_paperless_token(client: TestClient) -> None:
    connect_page = client.get("/ui/connect")
    csrf = connect_page.text.split('name="csrf_token" value="')[1].split('"')[0]
    secret = "super-secret-paperless-token-value"
    connected = client.post(
        "/ui/connect",
        data={"csrf_token": csrf, "paperless_token": secret},
        follow_redirects=False,
    )
    assert connected.status_code == 303

    set_cookie = connected.headers.get("set-cookie", "")
    assert "atlasdocs_sid=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie or "SameSite=Lax" in set_cookie
    assert secret not in set_cookie
    assert "Token " not in set_cookie
    assert f"Token {secret}" not in set_cookie

    cookie_value = client.cookies.get("atlasdocs_sid")
    assert cookie_value
    assert secret not in cookie_value
    assert "Token" not in cookie_value

    stored = session_store.get(cookie_value)
    assert stored is not None
    assert stored.paperless_authorization == f"Token {secret}"


def test_ui_logout_invalidates_server_session(client: TestClient) -> None:
    connect_page = client.get("/ui/connect")
    csrf = connect_page.text.split('name="csrf_token" value="')[1].split('"')[0]
    client.post(
        "/ui/connect",
        data={"csrf_token": csrf, "paperless_token": "test-token"},
        follow_redirects=False,
    )
    sid = client.cookies.get("atlasdocs_sid")
    assert session_store.get(sid) is not None

    workbench = client.get("/ui")
    csrf = workbench.text.split('name="csrf_token" value="')[1].split('"')[0]
    disconnected = client.post(
        "/ui/disconnect",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert disconnected.status_code == 303
    assert session_store.get(sid) is None
    assert client.get("/ui", follow_redirects=False).status_code == 303


def test_ui_classify_via_post_form(client: TestClient) -> None:
    connect_page = client.get("/ui/connect")
    csrf = connect_page.text.split('name="csrf_token" value="')[1].split('"')[0]
    connected = client.post(
        "/ui/connect",
        data={"csrf_token": csrf, "paperless_token": "test-token"},
        follow_redirects=False,
    )
    assert connected.status_code == 303

    detail = client.get("/ui/documents/184")
    assert detail.status_code == 200
    assert "Payslip Germany" in detail.text
    assert "test-token" not in detail.text
    csrf = detail.text.split('name="csrf_token" value="')[1].split('"')[0]

    classified = client.post(
        "/ui/documents/184/relationships",
        data={
            "csrf_token": csrf,
            "relationship": "source-country",
            "target": "Germany",
            "page": "1",
        },
        follow_redirects=True,
    )
    assert classified.status_code == 200
    assert "source-country" in classified.text
    assert "Germany" in classified.text
    assert "test-token" not in classified.text
