"""v0.6 Phase B: entity registry, constraints, completeness, Explore API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlasdocs.db.models import Entity, RelationshipStatus
from atlasdocs.db.session import get_session_factory
from atlasdocs.services.completeness import CompletenessInput, calculate_completeness
from atlasdocs.services.entity_types import list_entity_types, registry_code_for_ontology

AUTH = {"Authorization": "Token test-token"}


def test_entity_type_registry_endpoint(client: TestClient) -> None:
    assert client.get("/entity-types").status_code == 401
    response = client.get("/entity-types", headers=AUTH)
    assert response.status_code == 200
    codes = [item["code"] for item in response.json()]
    assert codes == [item.code for item in list_entity_types()]
    assert response.json()[0]["searchable"] is True


def test_completeness_calculator_rules() -> None:
    assert (
        calculate_completeness(
            CompletenessInput(
                registry_type="document",
                confirmed_relationship_codes=frozenset(),
                has_suggested_relationships=False,
            )
        )
        == "empty"
    )
    assert (
        calculate_completeness(
            CompletenessInput(
                registry_type="document",
                confirmed_relationship_codes=frozenset({"source-country"}),
                has_suggested_relationships=False,
            )
        )
        == "partial"
    )
    assert (
        calculate_completeness(
            CompletenessInput(
                registry_type="document",
                confirmed_relationship_codes=frozenset({"document-type", "source-country"}),
                has_suggested_relationships=False,
            )
        )
        == "classified"
    )
    assert (
        calculate_completeness(
            CompletenessInput(
                registry_type="document",
                confirmed_relationship_codes=frozenset({"document-type"}),
                has_suggested_relationships=True,
            )
        )
        == "needs_review"
    )
    assert registry_code_for_ontology("person") == "person"
    assert registry_code_for_ontology("document-type") == "concept"


def test_relationship_target_constraint_rejects_wrong_type(client: TestClient) -> None:
    # replies-to accepts documents only; Alice is a person registry type.
    alice = client.get(
        "/entities/search",
        headers=AUTH,
        params={"q": "Alice", "entity_type": "person"},
    ).json()[0]
    source = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "document-type", "target": "payslip"},
    ).json()["entity_id"]
    response = client.post(
        f"/entities/{source}/relationships",
        headers=AUTH,
        json={"relationship": "replies-to", "target_entity_id": alice["id"]},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    text = detail if isinstance(detail, str) else str(detail)
    assert "not valid" in text.lower()


def test_replies_to_requires_document_target(client: TestClient) -> None:
    response = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "replies-to", "target": "Germany"},
    )
    assert response.status_code == 422


def test_document_completeness_transitions(client: TestClient) -> None:
    created = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "source-country", "target": "Germany"},
    )
    assert created.status_code == 201
    assert created.json()["semantic_completeness"] == "partial"

    classified = client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "document-type", "target": "Payslip"},
    )
    assert classified.status_code == 201
    assert classified.json()["semantic_completeness"] == "classified"

    session = get_session_factory()()
    try:
        entity_id = created.json()["entity_id"]
        entity = session.get(Entity, __import__("uuid").UUID(entity_id))
        assert entity is not None
        assert entity.semantic_completeness == "classified"
    finally:
        session.close()


def test_suggested_relationship_marks_needs_review(client: TestClient) -> None:
    detail = client.get("/documents/184", headers=AUTH)
    assert detail.status_code == 200
    # Ensure entity exists first via a confirmed edge, then add a suggestion via entity API.
    client.post(
        "/documents/184/relationships",
        headers=AUTH,
        json={"relationship": "document-type", "target": "Payslip"},
    )
    entity_id = client.get("/documents/184", headers=AUTH).json()["entity_id"]
    suggested = client.post(
        f"/entities/{entity_id}/relationships",
        headers=AUTH,
        json={
            "relationship": "source-country",
            "target": "Germany",
            "status": "suggested",
        },
    )
    assert suggested.status_code == 201
    assert suggested.json()["semantic_completeness"] == "needs_review"
    assert any(
        rel["status"] == RelationshipStatus.suggested.value
        for rel in suggested.json()["relationships"]
    )


def test_explore_documents_and_people(client: TestClient) -> None:
    assert client.get("/explore").status_code == 401
    docs = client.get("/explore", headers=AUTH, params={"mode": "documents", "page": 1})
    assert docs.status_code == 200
    body = docs.json()
    assert body["mode"] == "document"
    assert body["page"] == 1
    assert isinstance(body["items"], list)
    assert body["items"], "expected at least one authorized document"
    item = body["items"][0]
    assert item["entity_type"] == "document"
    assert "semantic_completeness" in item
    assert "relationship_summary" in item
    assert item["preview_available"] is True

    people = client.get("/explore", headers=AUTH, params={"mode": "people", "q": "Ali"})
    assert people.status_code == 200
    assert people.json()["mode"] == "person"
    labels = {row["label"] for row in people.json()["items"]}
    assert "Alice" in labels
    assert all(row["entity_type"] == "person" for row in people.json()["items"])


def test_entity_search_registry_types(client: TestClient) -> None:
    people = client.get(
        "/entities/search",
        headers=AUTH,
        params={"q": "Ali", "entity_type": "person"},
    )
    assert people.status_code == 200
    assert {row["label"] for row in people.json()} == {"Alice"}
    assert people.json()[0]["entity_type"] == "person"

    csrf = client.get("/ui/api/session").json()["csrf_token"]
    connected = client.post(
        "/ui/api/connect",
        json={"csrf_token": csrf, "paperless_token": "test-token"},
    )
    assert connected.status_code == 200
    bff = client.get("/ui/api/explore", params={"mode": "countries"})
    assert bff.status_code == 200
    assert bff.json()["mode"] == "country"
