"""Phase E: session exposes username_label for account menu."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.fakes import FakePaperlessTransport


def test_session_includes_username_label_after_login(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    paperless_transport.next_token = "exchanged-token"
    logged_in = client.post(
        "/ui/api/login",
        json={"username": "ada", "password": "correct-horse", "csrf_token": csrf},
    )
    assert logged_in.status_code == 200
    body = logged_in.json()
    assert body["authenticated"] is True
    assert body["username_label"] == "ada"
    assert "exchanged-token" not in logged_in.text

    session = client.get("/ui/api/session").json()
    assert session["authenticated"] is True
    assert session["username_label"] == "ada"


def test_session_username_label_null_when_anonymous(client: TestClient) -> None:
    body = client.get("/ui/api/session").json()
    assert body["authenticated"] is False
    assert body.get("username_label") is None
