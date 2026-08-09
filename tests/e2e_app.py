"""Uvicorn entrypoint for Playwright: mocked Paperless, seeded SQLite, ingest worker."""

from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("ATLASDOCS_ENV", "development")
os.environ.setdefault("SESSION_SECRET", "e2e-session-secret")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "e2e-token-encryption-key")
os.environ.setdefault("SESSION_SECURE", "false")
os.environ.setdefault("PAPERLESS_PUBLIC_URL", "http://paperless.example.test")

from atlasdocs.api import create_app  # noqa: E402
from atlasdocs.config import get_settings  # noqa: E402
from atlasdocs.db.models import Base  # noqa: E402
from atlasdocs.db.seed import seed_from_path  # noqa: E402
from atlasdocs.db.session import get_db, get_engine, get_session_factory, reset_engine  # noqa: E402
from atlasdocs.services.ingest import IngestionWorker  # noqa: E402
from atlasdocs.services.paperless import PaperlessClient  # noqa: E402
from tests.fakes import FakePaperlessTransport  # noqa: E402

SEED_PATH = Path(__file__).resolve().parents[1] / "config" / "seed" / "v0.1.yaml"
_DB = Path(tempfile.gettempdir()) / "atlasdocs-e2e.sqlite"

get_settings.cache_clear()
reset_engine()
if _DB.exists():
    _DB.unlink()

engine = get_engine(f"sqlite+pysqlite:///{_DB}")
Base.metadata.create_all(engine)
session = get_session_factory()()
try:
    seed_from_path(session, SEED_PATH)
    session.commit()
finally:
    session.close()

_transport = FakePaperlessTransport()
# Password login for Playwright
_transport.valid_credentials = {"ada": "correct-horse"}
_transport.next_token = "e2e-exchanged-token"

app = create_app()


def _override_db():
    db = get_session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _override_paperless() -> PaperlessClient:
    return PaperlessClient(base_url="http://paperless.test", transport=_transport)


from atlasdocs.api.routes import get_paperless_client  # noqa: E402

app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_paperless_client] = _override_paperless


def _worker_loop() -> None:
    while True:
        db = get_session_factory()()
        try:
            worker = IngestionWorker(
                db,
                PaperlessClient(base_url="http://paperless.test", transport=_transport),
            )
            worker.run_once()
        except Exception:
            db.rollback()
        finally:
            db.close()
        time.sleep(0.2)


_thread = threading.Thread(target=_worker_loop, name="e2e-ingest-worker", daemon=True)
_thread.start()
