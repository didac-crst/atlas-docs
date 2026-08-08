from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from atlasdocs.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _as_url(url: str | URL) -> URL:
    return make_url(url) if isinstance(url, str) else url


def get_engine(url: str | URL | None = None) -> Engine:
    global _engine, _SessionLocal
    database_url = _as_url(url) if url is not None else get_settings().sqlalchemy_url()

    # Compare URL objects directly: str(URL) masks passwords and can miss changes.
    if _engine is not None and url is not None and _engine.url != database_url:
        _engine.dispose()
        _engine = None
        _SessionLocal = None

    if _engine is None:
        connect_args = {}
        if database_url.get_backend_name() == "sqlite":
            connect_args["check_same_thread"] = False
        _engine = create_engine(database_url, connect_args=connect_args)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
