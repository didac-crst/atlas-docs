"""BFF authn/CSRF and token non-leakage for the React workbench API."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _connect(client: TestClient, token: str = "super-secret-paperless-token") -> str:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    connected = client.post(
        "/ui/api/connect",
        json={"csrf_token": csrf, "paperless_token": token},
    )
    assert connected.status_code == 200
    assert token not in connected.text
    return connected.json()["csrf_token"]


def test_bff_rejects_unauthenticated_requests(client: TestClient) -> None:
    assert client.get("/ui/api/documents").status_code == 401
    assert client.get("/ui/api/documents/184").status_code == 401
    assert client.get("/ui/api/relationship-types").status_code == 401
    assert client.get("/ui/api/concepts").status_code == 401
    assert (
        client.post(
            "/ui/api/documents/184/relationships",
            headers={"X-CSRF-Token": "anything"},
            json={"relationship": "source-country", "target": "germany"},
        ).status_code
        == 401
    )
    assert (
        client.delete(
            "/ui/api/relationships/00000000-0000-0000-0000-000000000000",
            headers={"X-CSRF-Token": "anything"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/ui/api/reconcile",
            headers={"X-CSRF-Token": "anything"},
            json={"dry_run": True},
        ).status_code
        == 401
    )


def test_csrf_protects_relationship_mutations(client: TestClient) -> None:
    csrf = _connect(client)
    missing = client.post(
        "/ui/api/documents/184/relationships",
        json={"relationship": "source-country", "target": "germany"},
    )
    assert missing.status_code == 400
    assert "Invalid CSRF token" in missing.text

    wrong = client.post(
        "/ui/api/documents/184/relationships",
        headers={"X-CSRF-Token": "not-the-session-csrf"},
        json={"relationship": "source-country", "target": "germany"},
    )
    assert wrong.status_code == 400
    assert "Invalid CSRF token" in wrong.text

    created = client.post(
        "/ui/api/documents/184/relationships",
        headers={"X-CSRF-Token": csrf},
        json={"relationship": "source-country", "target": "germany"},
    )
    assert created.status_code == 201
    rel_id = next(
        item["id"] for item in created.json()["relationships"] if item["type"] == "source-country"
    )
    assert "super-secret-paperless-token" not in created.text

    # CSRF rotated after successful mutation.
    stale = client.delete(
        f"/ui/api/relationships/{rel_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert stale.status_code == 400

    fresh = client.get("/ui/api/session").json()["csrf_token"]
    deleted = client.delete(
        f"/ui/api/relationships/{rel_id}",
        headers={"X-CSRF-Token": fresh},
    )
    assert deleted.status_code == 204


def test_bff_responses_never_include_paperless_token(client: TestClient) -> None:
    secret = "leak-check-token-value-xyz"
    csrf = _connect(client, token=secret)
    paths = [
        client.get("/ui/api/session"),
        client.get("/ui/api/documents"),
        client.get("/ui/api/documents/184"),
        client.get("/ui/api/relationship-types"),
        client.get("/ui/api/concepts?q=ger"),
        client.post(
            "/ui/api/documents/184/relationships",
            headers={"X-CSRF-Token": csrf},
            json={"relationship": "document-type", "target": "payslip"},
        ),
    ]
    for response in paths:
        assert response.status_code in {200, 201}
        assert secret not in response.text
        assert "paperless_token" not in response.text
        assert "paperless_authorization" not in response.text
        body = response.json()
        dumped = str(body)
        assert secret not in dumped
        assert "paperless_authorization" not in dumped
