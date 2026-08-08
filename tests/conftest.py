from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Must run before test modules import atlasdocs.api (which builds the app at import).
os.environ.setdefault("ATLASDOCS_ENV", "development")

from atlasdocs.api import create_app
from atlasdocs.config import get_settings
from atlasdocs.db.models import Base
from atlasdocs.db.seed import seed_from_path
from atlasdocs.db.session import get_db, get_engine, get_session_factory, reset_engine
from atlasdocs.services.login_rate_limit import login_rate_limiter
from atlasdocs.services.paperless import PaperlessClient
from tests.fakes import FakePaperlessTransport

SEED_PATH = Path(__file__).resolve().parents[1] / "config" / "seed" / "v0.1.yaml"
AUTH = {"Authorization": "Token test-token"}


@pytest.fixture()
def paperless_transport() -> FakePaperlessTransport:
    return FakePaperlessTransport()


@pytest.fixture()
def client(paperless_transport: FakePaperlessTransport, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-token-encryption-key")
    monkeypatch.setenv("ATLASDOCS_ENV", "development")
    monkeypatch.setenv("SESSION_SECURE", "false")
    monkeypatch.setenv("PAPERLESS_PUBLIC_URL", "http://paperless.example.test")
    monkeypatch.delenv("PAPERLESS_BASE_URL", raising=False)
    get_settings.cache_clear()
    login_rate_limiter.clear()
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

    app.dependency_overrides[get_db] = override_db
    from atlasdocs.api.routes import get_paperless_client

    app.dependency_overrides[get_paperless_client] = override_paperless

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    login_rate_limiter.clear()
    reset_engine()
    get_settings.cache_clear()
