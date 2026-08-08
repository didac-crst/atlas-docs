from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from atlasdocs.api import create_app
from atlasdocs.db.models import Base, Concept, DocumentReference, RelationshipType
from atlasdocs.db.seed import seed_from_path
from atlasdocs.db.session import get_db, get_engine, get_session_factory, reset_engine
from atlasdocs.services.paperless import PaperlessClient

SEED_PATH = Path(__file__).resolve().parents[1] / "config" / "seed" / "v0.1.yaml"


class FakePaperlessTransport(httpx.BaseTransport):
    """Deterministic Paperless REST stand-in. No real HTTP or Paperless DB."""

    def __init__(self) -> None:
        self.documents: dict[int, dict] = {184: {"id": 184, "title": "Payslip"}}
        self.denied: set[int] = set()
        self.unauthorized: set[int] = set()
        self.server_error: set[int] = set()
        self.timeout: set[int] = set()
        self.calls: list[int] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        document_id = int(request.url.path.rstrip("/").split("/")[-1])
        self.calls.append(document_id)

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
def client(paperless_transport: FakePaperlessTransport, tmp_path: Path):
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
    reset_engine()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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
        json={"relationship": "source-country", "target": "Germany"},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["paperless_document_id"] == 184
    assert body["relationships"] == [
        {
            "type": "source-country",
            "target": "Germany",
            "origin": "manual",
            "status": "confirmed",
        }
    ]

    fetched = client.get("/documents/184")
    assert fetched.status_code == 200
    assert fetched.json() == body

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
    assert 999 in paperless_transport.calls


def test_duplicate_relationship_rejected(client: TestClient) -> None:
    payload = {"relationship": "source-country", "target": "Germany"}
    assert client.post("/documents/184/relationships", json=payload).status_code == 201
    duplicate = client.post("/documents/184/relationships", json=payload)
    assert duplicate.status_code == 409


def test_invalid_target_rejected(client: TestClient) -> None:
    response = client.post(
        "/documents/184/relationships",
        json={"relationship": "source-country", "target": "Atlantis"},
    )
    assert response.status_code == 400


def test_invalid_relationship_type_rejected(client: TestClient) -> None:
    response = client.post(
        "/documents/184/relationships",
        json={"relationship": "issued-by", "target": "Germany"},
    )
    assert response.status_code == 400


def test_paperless_server_error(client: TestClient, paperless_transport: FakePaperlessTransport) -> None:
    paperless_transport.server_error.add(184)
    response = client.get("/documents/184")
    assert response.status_code == 502


def test_paperless_timeout(client: TestClient, paperless_transport: FakePaperlessTransport) -> None:
    paperless_transport.timeout.add(184)
    response = client.get("/documents/184")
    assert response.status_code == 502


def test_authorization_boundary_hides_document(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    # Pre-create semantics while access is allowed.
    assert (
        client.post(
            "/documents/184/relationships",
            json={"relationship": "document-type", "target": "Payslip"},
        ).status_code
        == 201
    )

    paperless_transport.denied.add(184)
    response = client.get("/documents/184")
    assert response.status_code == 404
    assert "relationships" not in response.json() or "detail" in response.json()


def test_paperless_client_uses_rest_only() -> None:
    source = Path(__file__).resolve().parents[1] / "src" / "atlasdocs" / "services" / "paperless.py"
    text = source.read_text(encoding="utf-8")
    assert "psycopg" not in text
    assert "sqlalchemy" not in text
    assert "/api/documents/" in text
