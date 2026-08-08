"""PAPERLESS_PUBLIC_URL browser link construction."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ATLASDOCS_ENV", "development")

from atlasdocs.api import create_app
from atlasdocs.config import Settings, get_settings
from atlasdocs.db.models import Base
from atlasdocs.db.seed import seed_from_path
from atlasdocs.db.session import get_db, get_engine, get_session_factory, reset_engine
from atlasdocs.services.paperless import PaperlessClient
from tests.fakes import FakePaperlessTransport

SEED_PATH = Path(__file__).resolve().parents[1] / "config" / "seed" / "v0.1.yaml"
AUTH = {"Authorization": "Token secret-token"}


def test_paperless_document_url_uses_public_origin_only() -> None:
    settings = Settings(
        atlasdocs_env="development",
        paperless_base_url="http://paperless:8000",
        paperless_public_url="https://docs.example.test",
    )
    url = settings.paperless_document_url(184)
    assert url == "https://docs.example.test/documents/184/"
    assert "paperless:8000" not in url
    assert "Token" not in url
    assert "Bearer" not in url
    assert "@" not in url


def test_paperless_document_url_missing_public_returns_none() -> None:
    settings = Settings(
        atlasdocs_env="development",
        paperless_base_url="http://host.docker.internal:8000",
        paperless_public_url=None,
    )
    assert settings.paperless_document_url(184) is None

    blank = Settings(
        atlasdocs_env="development",
        paperless_base_url="http://host.docker.internal:8000",
        paperless_public_url="   ",
    )
    assert blank.paperless_document_url(184) is None


def test_paperless_document_url_strips_trailing_slash() -> None:
    settings = Settings(
        atlasdocs_env="development",
        paperless_public_url="https://docs.example.test/",
    )
    assert settings.paperless_document_url(12) == "https://docs.example.test/documents/12/"


def test_paperless_public_url_rejects_credentials_and_non_http() -> None:
    with pytest.raises(Exception):
        Settings(
            atlasdocs_env="development",
            paperless_public_url="https://user:password@docs.example.test",
        )
    with pytest.raises(Exception):
        Settings(
            atlasdocs_env="development",
            paperless_public_url="ftp://docs.example.test",
        )


@contextmanager
def _client_with_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: str
) -> Iterator[TestClient]:
    get_settings.cache_clear()
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-token-encryption-key")
    monkeypatch.setenv("ATLASDOCS_ENV", "development")
    monkeypatch.setenv("SESSION_SECURE", "false")
    monkeypatch.setenv("PAPERLESS_BASE_URL", "http://host.docker.internal:8000")
    for key in ("PAPERLESS_PUBLIC_URL",):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    reset_engine()

    engine = get_engine(f"sqlite+pysqlite:///{tmp_path / 'atlasdocs.db'}")
    Base.metadata.create_all(engine)
    session = get_session_factory()()
    seed_from_path(session, SEED_PATH)
    session.commit()
    session.close()

    transport = FakePaperlessTransport()
    app = create_app()

    def override_db():
        db = get_session_factory()()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def override_paperless() -> PaperlessClient:
        return PaperlessClient(base_url="http://paperless.test", transport=transport)

    app.dependency_overrides[get_db] = override_db
    from atlasdocs.api.routes import get_paperless_client

    app.dependency_overrides[get_paperless_client] = override_paperless
    with TestClient(app) as client:
        try:
            yield client
        finally:
            app.dependency_overrides.clear()
            reset_engine()
            get_settings.cache_clear()


def test_api_open_url_null_when_public_url_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with _client_with_env(monkeypatch, tmp_path) as client:
        response = client.get("/documents/184", headers=AUTH)
        assert response.status_code == 200
        assert response.json()["open_url"] is None
        assert "host.docker.internal" not in response.text
        assert "secret-token" not in response.text


def test_api_open_url_uses_public_url_without_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with _client_with_env(
        monkeypatch, tmp_path, PAPERLESS_PUBLIC_URL="https://paperless.example.test"
    ) as client:
        response = client.get("/documents/184", headers=AUTH)
        assert response.status_code == 200
        body = response.json()
        assert body["open_url"] == "https://paperless.example.test/documents/184/"
        assert "secret-token" not in response.text
        assert "Token" not in body["open_url"]
        assert "host.docker.internal" not in body["open_url"]
        assert "://" in body["open_url"]
