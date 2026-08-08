"""v0.5 product refinement: home summaries and entity search."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from tests.conftest import AUTH
from tests.fakes import FakePaperlessTransport


def _connect(client: TestClient) -> str:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    response = client.post(
        "/ui/api/connect",
        json={"csrf_token": csrf, "paperless_token": "test-token"},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_home_summary_authz_safe(client: TestClient) -> None:
    _connect(client)
    response = client.get("/ui/api/home")
    assert response.status_code == 200
    body = response.json()
    for key in (
        "needs_classification",
        "needs_review",
        "failed_ingestion",
        "reconciliation_issues",
    ):
        assert "count" in body[key]
        assert isinstance(body[key]["count"], int)
        assert body[key]["count"] >= 0
    assert isinstance(body["recent_documents"], list)
    assert isinstance(body["recent_knowledge"], list)
    assert "Token" not in response.text
    assert "test-token" not in response.text


def test_entity_search_concepts(client: TestClient) -> None:
    _connect(client)
    response = client.get("/ui/api/entities/search", params={"q": "Ger", "entity_type": "concept"})
    assert response.status_code == 200
    hits = response.json()
    assert hits
    assert all(item["entity_type"] == "concept" for item in hits)
    assert all("id" in item and "label" in item for item in hits)
    assert all(item.get("paperless_document_id") is None for item in hits)


def test_entity_search_documents(client: TestClient) -> None:
    _connect(client)
    response = client.get(
        "/ui/api/entities/search", params={"q": "Payslip", "entity_type": "document"}
    )
    assert response.status_code == 200
    hits = response.json()
    assert hits
    assert all(item["entity_type"] == "document" for item in hits)
    assert all(item.get("paperless_document_id") is not None for item in hits)
    assert all(item.get("open_url") is None or "paperless.example.test" in item["open_url"] for item in hits)


def test_documents_filter_by_correspondent(client: TestClient) -> None:
    response = client.get(
        "/documents",
        headers=AUTH,
        params={
            "classification": "any",
            "correspondent": "Acme",
            "sort": "title",
            "order": "asc",
        },
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert all("Acme" in (item.get("correspondent") or "") for item in items)


def test_unclassified_oldest_uses_ascending_order(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.calls.clear()
    response = client.get(
        "/documents",
        headers=AUTH,
        params={"classification": "unclassified", "sort": "created", "order": "asc"},
    )
    assert response.status_code == 200
    list_calls = [call for call in paperless_transport.calls if "GET /api/documents/" in call]
    assert list_calls
    orderings: list[str] = []
    for call in list_calls:
        query = parse_qs(urlparse(call.split(" ", 1)[1]).query)
        values = query.get("ordering", [])
        assert values, call
        orderings.append(values[0])
    assert orderings
    assert all(value == "created" for value in orderings)

def test_relationship_via_target_entity_id(client: TestClient) -> None:
    _connect(client)
    concepts = client.get("/ui/api/entities/search", params={"q": "Germany", "entity_type": "concept"})
    entity_id = concepts.json()[0]["id"]
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    created = client.post(
        "/ui/api/documents/184/relationships",
        headers={"X-CSRF-Token": csrf},
        json={"relationship": "source-country", "target_entity_id": entity_id},
    )
    assert created.status_code == 201
    types = [rel["type"] for rel in created.json()["relationships"]]
    assert "source-country" in types
