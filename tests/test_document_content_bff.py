"""BFF preview/download proxy tests."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from atlasdocs.services.ingest import spool_dir
from atlasdocs.services.paperless import PaperlessAuthError, PaperlessClient
from tests.fakes import FakePaperlessTransport


def _connect(client: TestClient, token: str = "bff-content-token") -> None:
    csrf = client.get("/ui/api/session").json()["csrf_token"]
    response = client.post(
        "/ui/api/connect",
        json={"csrf_token": csrf, "paperless_token": token},
    )
    assert response.status_code == 200


def _count_spool_files() -> int:
    root = spool_dir()
    if not root.exists():
        return 0
    return sum(1 for path in root.iterdir() if path.is_file())


def test_authenticated_preview_succeeds(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    spool_before = _count_spool_files()
    response = client.get("/ui/api/documents/184/preview")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("application/pdf")
    assert response.headers.get("content-disposition", "").startswith("inline;")
    assert response.headers.get("cache-control") == "no-store"
    assert response.content.startswith(b"%PDF-fake-preview")
    assert "bff-content-token" not in response.text
    assert "Token " not in response.text
    assert _count_spool_files() == spool_before


def test_authenticated_download_succeeds(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    _connect(client)
    response = client.get("/ui/api/documents/184/download")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("application/pdf")
    disposition = response.headers.get("content-disposition", "")
    assert disposition.startswith("attachment;")
    assert 'filename="Payslip Germany"' in disposition
    assert response.content.startswith(b"%PDF-fake-download")
    assert "bff-content-token" not in response.text


def test_unauthenticated_preview_and_download_401(client: TestClient) -> None:
    assert client.get("/ui/api/documents/184/preview").status_code == 401
    assert client.get("/ui/api/documents/184/download").status_code == 401


def test_inaccessible_document_returns_404_without_leak(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.denied.add(999)
    paperless_transport.documents[999] = {"id": 999, "title": "Secret payroll"}
    _connect(client)
    preview = client.get("/ui/api/documents/999/preview")
    assert preview.status_code == 404
    assert preview.content in {b"", b'{"detail":"Document not found"}'}
    assert "Secret payroll" not in preview.text
    assert "bff-content-token" not in preview.text

    download = client.get("/ui/api/documents/999/download")
    assert download.status_code == 404
    assert "Secret payroll" not in download.text


def test_safe_filename_in_content_disposition(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.documents[777] = {
        "id": 777,
        "title": "../nested/report.pdf",
        "created_date": "2024-01-01",
    }
    _connect(client)
    response = client.get("/ui/api/documents/777/download")
    assert response.status_code == 200
    disposition = response.headers.get("content-disposition", "")
    assert "\n" not in disposition
    assert "\r" not in disposition
    assert 'filename="report.pdf"' in disposition


def test_response_never_contains_token_values(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    secret = "super-secret-paperless-token"
    _connect(client, token=secret)
    for path in ("/ui/api/documents/184/preview", "/ui/api/documents/184/download"):
        response = client.get(path)
        assert response.status_code == 200
        assert secret not in response.text
        assert "Token " not in response.text
        for value in response.headers.values():
            assert secret not in value
            assert "Token " not in value


def test_preview_rejects_svg_content_type(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.preview_content_type = "image/svg+xml"
    _connect(client)
    response = client.get("/ui/api/documents/184/preview")
    assert response.status_code == 415
    assert response.json()["detail"] == "Preview is only available for PDF and raster images"
    assert "bff-content-token" not in response.text


def test_preview_rejects_non_image_non_pdf(
    client: TestClient, paperless_transport: FakePaperlessTransport
) -> None:
    paperless_transport.preview_content_type = "application/octet-stream"
    _connect(client)
    response = client.get("/ui/api/documents/184/preview")
    assert response.status_code == 415
    assert response.json()["detail"] == "Preview is only available for PDF and raster images"


def test_fake_preview_download_require_authorization(
    paperless_transport: FakePaperlessTransport,
) -> None:
    """Regression: content endpoints must not serve bytes without Authorization."""
    paperless_transport.valid_tokens = {"accepted-token"}

    with pytest.raises(PaperlessAuthError):
        PaperlessClient(base_url="http://paperless.test", transport=paperless_transport).stream_document_file(
            "", 184, kind="preview"
        )

    wrong = httpx.Request(
        "GET",
        "http://paperless.test/api/documents/184/preview/",
        headers={"Authorization": "Token wrong"},
    )
    assert paperless_transport.handle_request(wrong).status_code == 401

    ok = httpx.Request(
        "GET",
        "http://paperless.test/api/documents/184/download/",
        headers={"Authorization": "Token accepted-token"},
    )
    assert paperless_transport.handle_request(ok).status_code == 200


def test_no_atlasdocs_disk_write_of_document_bytes(
    client: TestClient, paperless_transport: FakePaperlessTransport, tmp_path: Path, monkeypatch
) -> None:
    watch = tmp_path / "watch-spool"
    watch.mkdir()
    monkeypatch.setattr("atlasdocs.services.ingest.spool_dir", lambda: watch)
    _connect(client)
    before = list(watch.iterdir())
    response = client.get("/ui/api/documents/184/download")
    assert response.status_code == 200
    assert len(response.content) > 0
    after = list(watch.iterdir())
    assert before == after
