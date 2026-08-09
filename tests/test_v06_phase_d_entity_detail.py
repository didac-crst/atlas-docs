"""v0.6 Phase D: entity detail with backlinks and related documents."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import AUTH
from tests.fakes import FakePaperlessTransport


def test_entity_detail_includes_backlinks_and_related_documents(client: TestClient) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    )
    assert created.status_code == 201
    germany = client.get(
        "/entities/search",
        headers=AUTH,
        params={"q": "Germany", "entity_type": "country"},
    ).json()[0]
    detail = client.get(f"/entities/{germany['id']}", headers=AUTH)
    assert detail.status_code == 200
    body = detail.json()
    assert body["label"] == "Germany"
    assert body["display_type"] == "country"
    assert body["semantic_completeness"]
    assert any(item["type"] == "source-country" for item in body["backlinks"])
    assert any(item["source_paperless_document_id"] == 184 for item in body["backlinks"])
    assert any(item["paperless_document_id"] == 184 for item in body["related_documents"])
    assert all("id" in item and "origin" in item and "status" in item for item in body["backlinks"])


def test_entity_backlinks_hide_inaccessible_sources(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    )
    assert created.status_code == 201
    germany = client.get(
        "/entities/search",
        headers=AUTH,
        params={"q": "Germany", "entity_type": "country"},
    ).json()[0]
    paperless_transport.denied.add(184)
    detail = client.get(f"/entities/{germany['id']}", headers=AUTH)
    assert detail.status_code == 200
    assert detail.json()["backlinks"] == []
    assert detail.json()["related_documents"] == []


def test_ui_entity_detail_bff(client: TestClient) -> None:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    connected = client.post(
        "/ui/api/connect",
        json={"csrf_token": csrf, "paperless_token": "test-token"},
    )
    assert connected.status_code == 200
    client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "concerns-person", "target": "Alice"},
    )
    alice = client.get(
        "/ui/api/entities/search",
        params={"q": "Alice", "entity_type": "person"},
    ).json()[0]
    detail = client.get(f"/ui/api/entities/{alice['id']}")
    assert detail.status_code == 200
    assert detail.json()["label"] == "Alice"
    assert detail.json()["display_type"] == "person"
    assert any(item["paperless_document_id"] == 184 for item in detail.json()["related_documents"])
