"""v0.7 lifecycle, completeness, Explore, trash, downloads, and reconcile acceptance."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from atlasdocs.db.models import Entity
from atlasdocs.db.session import get_session_factory
from tests.conftest import AUTH
from tests.fakes import FakePaperlessTransport


def _connect(client: TestClient, token: str = "test-token") -> str:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    connected = client.post(
        "/ui/api/connect",
        json={"csrf_token": csrf, "paperless_token": token},
    )
    assert connected.status_code == 200
    return client.get("/ui/api/session").json()["csrf_token"]


def test_entity_types_expose_lifecycle_category(client: TestClient) -> None:
    rows = client.get("/entity-types", headers=AUTH).json()
    by_code = {row["code"]: row["lifecycle_category"] for row in rows}
    assert by_code["document"] == "evidence"
    assert by_code["person"] == "master_data"
    assert by_code["organization"] == "master_data"
    assert by_code["country"] == "master_data"
    assert by_code["concept"] == "master_data"
    assert by_code["case"] == "organizational"


def test_document_response_includes_lifecycle_category(client: TestClient) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    )
    assert created.status_code == 201
    detail = client.get("/documents/184", headers=AUTH).json()
    assert detail["lifecycle_category"] == "evidence"
    assert detail["trashed"] is False
    assert detail["semantic_completeness"] == "partial"


def test_creation_time_completeness_starts_empty(client: TestClient) -> None:
    created = client.post(
        "/reconcile",
        headers=AUTH,
        json={"dry_run": False},
    )
    assert created.status_code == 200
    detail = client.get("/documents/184", headers=AUTH).json()
    assert detail["entity_id"]
    assert detail["semantic_completeness"] == "empty"
    assert detail["lifecycle_category"] == "evidence"


def test_completeness_recalculates_on_add_remove_archive_restore(client: TestClient) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "concerns-person", "target": "Alice"},
    )
    assert created.status_code == 201
    assert created.json()["semantic_completeness"] == "partial"
    rel_id = created.json()["relationships"][0]["id"]

    alice = client.get(
        "/entities/search",
        headers=AUTH,
        params={"q": "Alice", "entity_type": "person"},
    ).json()[0]
    before = client.get(f"/entities/{alice['id']}", headers=AUTH).json()
    assert before["semantic_completeness"]

    archived = client.post(f"/entities/{alice['id']}/archive", headers=AUTH)
    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    assert archived.json()["semantic_completeness"]

    restored = client.post(f"/entities/{alice['id']}/restore", headers=AUTH)
    assert restored.status_code == 200
    assert restored.json()["archived"] is False

    removed = client.delete(f"/relationships/{rel_id}", headers=AUTH)
    assert removed.status_code == 204
    after_doc = client.get("/documents/184", headers=AUTH).json()
    assert after_doc["semantic_completeness"] == "empty"


def test_evidence_cannot_use_master_data_archive(client: TestClient) -> None:
    client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    )
    entity_id = client.get("/documents/184", headers=AUTH).json()["entity_id"]
    blocked = client.post(f"/entities/{entity_id}/archive", headers=AUTH)
    assert blocked.status_code in {400, 409, 422}


def test_organizational_case_can_archive_and_restore(client: TestClient) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "belongs-to", "target": "Sample Case"},
    )
    assert created.status_code == 201
    case = client.get(
        "/entities/search",
        headers=AUTH,
        params={"q": "Sample Case", "entity_type": "case"},
    ).json()[0]
    detail = client.get(f"/entities/{case['id']}", headers=AUTH).json()
    assert detail["lifecycle_category"] == "organizational"

    archived = client.post(f"/entities/{case['id']}/archive", headers=AUTH)
    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    assert archived.json()["lifecycle_category"] == "organizational"

    restored = client.post(f"/entities/{case['id']}/restore", headers=AUTH)
    assert restored.status_code == 200
    assert restored.json()["archived"] is False


def test_explore_knowledge_mode(client: TestClient) -> None:
    client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "concerns-person", "target": "Alice"},
    )
    page = client.get("/explore", headers=AUTH, params={"mode": "knowledge"})
    assert page.status_code == 200
    body = page.json()
    assert body["mode"] == "knowledge"
    assert any(item["label"] == "Alice" for item in body["items"])
    assert all(item["entity_type"] != "document" for item in body["items"])
    alice = next(item for item in body["items"] if item["label"] == "Alice")
    assert alice["lifecycle_category"] == "master_data"
    assert "relationship_count" in alice


def test_explore_documents_search_sort_and_pagination(client: TestClient) -> None:
    client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "document-type", "target": "Payslip"},
    )
    page = client.get(
        "/explore",
        headers=AUTH,
        params={"mode": "documents", "q": "Payslip", "sort": "title", "order": "asc", "page": 1},
    )
    assert page.status_code == 200
    body = page.json()
    assert body["mode"] == "documents"
    assert body["page"] == 1
    assert body["page_size"] >= 1
    assert any(item["entity_type"] == "document" for item in body["items"])
    for item in body["items"]:
        if item["entity_type"] == "document":
            assert item["lifecycle_category"] == "evidence"
            assert "thumbnail_available" in item
            assert "relationship_count" in item


def test_explore_hides_trashed_documents(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    )
    client.request(
        "DELETE",
        "/documents/184",
        headers=AUTH,
        json={"confirm": True, "permanent": False},
    )
    page = client.get("/explore", headers=AUTH, params={"mode": "documents"})
    assert page.status_code == 200
    assert all(item.get("paperless_document_id") != 184 for item in page.json()["items"])


def test_evidence_trash_restore_and_permanent_delete(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    )
    trashed = client.request(
        "DELETE",
        "/documents/184",
        headers=AUTH,
        json={"confirm": True, "permanent": False},
    )
    assert trashed.status_code == 204
    assert 184 in paperless_transport.trashed_documents
    assert 184 not in paperless_transport.documents
    detail = client.get("/documents/184", headers=AUTH)
    assert detail.status_code == 200
    assert detail.json()["trashed"] is True

    restored = client.post("/documents/184/restore", headers=AUTH)
    assert restored.status_code == 204
    assert 184 in paperless_transport.documents
    assert client.get("/documents/184", headers=AUTH).json()["trashed"] is False

    client.request(
        "DELETE",
        "/documents/184",
        headers=AUTH,
        json={"confirm": True, "permanent": False},
    )
    purged = client.request(
        "DELETE",
        "/documents/184",
        headers=AUTH,
        json={"confirm": True, "permanent": True},
    )
    assert purged.status_code == 204
    assert client.get("/documents/184", headers=AUTH).status_code == 404
    assert client.get("/explore", headers=AUTH, params={"mode": "documents"}).status_code == 200


def test_master_data_cannot_delete_while_linked(client: TestClient) -> None:
    client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "concerns-person", "target": "Alice"},
    )
    alice = client.get(
        "/entities/search",
        headers=AUTH,
        params={"q": "Alice", "entity_type": "person"},
    ).json()[0]
    blocked = client.request(
        "DELETE",
        f"/entities/{alice['id']}",
        headers=AUTH,
        json={"confirm": True},
    )
    assert blocked.status_code == 409
    assert "relationships" in blocked.json()["detail"].lower()

    archived = client.post(f"/entities/{alice['id']}/archive", headers=AUTH)
    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    assert archived.json()["lifecycle_category"] == "master_data"

    restored = client.post(f"/entities/{alice['id']}/restore", headers=AUTH)
    assert restored.status_code == 200
    assert restored.json()["archived"] is False

    renamed = client.post(
        f"/entities/{alice['id']}/rename",
        headers=AUTH,
        json={"display_name": "Alicia"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["label"] == "Alicia"


def test_merge_placeholder_records_redirect(client: TestClient) -> None:
    client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "concerns-person", "target": "Alice"},
    )
    client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "concerns-person", "target": "Bob"},
    )
    alice = client.get(
        "/entities/search",
        headers=AUTH,
        params={"q": "Alice", "entity_type": "person"},
    ).json()[0]
    bob = client.get(
        "/entities/search",
        headers=AUTH,
        params={"q": "Bob", "entity_type": "person"},
    ).json()[0]
    merged = client.post(
        f"/entities/{alice['id']}/merge",
        headers=AUTH,
        json={"target_entity_id": bob["id"]},
    )
    assert merged.status_code == 200
    body = merged.json()
    assert body["merged_into_entity_id"] == bob["id"]
    assert body["archived"] is True


def test_download_variants_forward_query_and_secure_headers(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client, token="bff-download-token")
    original = client.get("/ui/api/documents/184/download", params={"original": "true"})
    assert original.status_code == 200
    assert original.headers.get("cache-control") == "no-store"
    assert original.headers.get("x-content-type-options") == "nosniff"
    assert "bff-download-token" not in original.text
    assert any("original=true" in call for call in paperless_transport.calls)

    versioned = client.get("/ui/api/documents/184/download", params={"version": "7"})
    assert versioned.status_code == 200
    assert versioned.headers.get("cache-control") == "no-store"
    assert versioned.headers.get("x-content-type-options") == "nosniff"
    assert "bff-download-token" not in versioned.text
    assert any("version=7" in call for call in paperless_transport.calls)


def test_document_detail_includes_versions(client: TestClient) -> None:
    detail = client.get("/documents/184", headers=AUTH).json()
    assert isinstance(detail.get("versions"), list)
    assert detail["versions"]
    assert "id" in detail["versions"][0]


def test_reconcile_reports_trashed_documents(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    )
    client.request(
        "DELETE",
        "/documents/184",
        headers=AUTH,
        json={"confirm": True, "permanent": False},
    )
    csrf = _connect(client)
    result = client.post(
        "/ui/api/reconcile",
        headers={"X-CSRF-Token": csrf},
        json={"dry_run": True},
    )
    assert result.status_code == 200
    body = result.json()
    assert 184 in body["trashed_in_paperless"]
    assert "Token " not in result.text
    assert "bff-download-token" not in result.text


def test_tombstone_hides_metadata_after_permanent_delete(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    )
    entity_id = created.json()["entity_id"]
    client.request(
        "DELETE",
        "/documents/184",
        headers=AUTH,
        json={"confirm": True, "permanent": True},
    )
    assert client.get("/documents/184", headers=AUTH).status_code == 404
    assert client.get(f"/entities/{entity_id}", headers=AUTH).status_code == 404
    explore = client.get("/explore", headers=AUTH, params={"mode": "documents", "q": "Payslip"})
    assert explore.status_code == 200
    assert all(item.get("paperless_document_id") != 184 for item in explore.json()["items"])

    db = get_session_factory()()
    try:
        entity = db.get(Entity, uuid.UUID(entity_id))
        assert entity is not None
        assert entity.deleted_at is not None
    finally:
        db.close()
