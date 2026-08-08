import pytest
from pydantic import ValidationError

from atlasdocs.config import (
    DEFAULT_DATABASE_PASSWORD,
    DEFAULT_SESSION_SECRET,
    DEFAULT_TOKEN_ENCRYPTION_KEY,
    Settings,
    get_settings,
)
from atlasdocs.db.models import Base
from atlasdocs.db.session import get_engine, get_session_factory, reset_engine
from atlasdocs.security.tokens import DEFAULT_TOKEN_ENCRYPTION_KEY as TOK_DEFAULT
from atlasdocs.ui.sessions import DbSessionStore


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_production_requires_non_default_session_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            atlasdocs_env="production",
            session_secret=DEFAULT_SESSION_SECRET,
            session_secure=True,
            database_password="production-db-password",
            token_encryption_key="production-token-key",
        )


def test_production_rejects_blank_session_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            atlasdocs_env="production",
            session_secret="   ",
            session_secure=True,
            database_password="production-db-password",
            token_encryption_key="production-token-key",
        )


def test_production_requires_secure_cookies() -> None:
    with pytest.raises(ValidationError):
        Settings(
            atlasdocs_env="production",
            session_secret="production-secret",
            session_secure=False,
            database_password="production-db-password",
            token_encryption_key="production-token-key",
        )


def test_production_rejects_default_database_password() -> None:
    with pytest.raises(ValidationError):
        Settings(
            atlasdocs_env="production",
            session_secret="production-secret",
            session_secure=True,
            database_password=DEFAULT_DATABASE_PASSWORD,
            token_encryption_key="production-token-key",
        )


def test_production_requires_non_default_token_encryption_key() -> None:
    with pytest.raises(ValidationError):
        Settings(
            atlasdocs_env="production",
            session_secret="production-secret",
            session_secure=True,
            database_password="production-db-password",
            token_encryption_key=DEFAULT_TOKEN_ENCRYPTION_KEY,
        )
    with pytest.raises(ValidationError):
        Settings(
            atlasdocs_env="production",
            session_secret="production-secret",
            session_secure=True,
            database_password="production-db-password",
            token_encryption_key=TOK_DEFAULT,
        )


def test_production_cookie_secure_forced() -> None:
    settings = Settings(
        atlasdocs_env="production",
        session_secret="production-secret",
        session_secure=True,
        database_password="production-db-password",
        token_encryption_key="production-token-key",
    )
    assert settings.cookie_secure is True
    assert settings.database_password.get_secret_value() == "production-db-password"


@pytest.mark.parametrize("value", [0, -1])
def test_rejects_non_positive_unclassified_max_upstream_pages(value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(atlasdocs_env="development", unclassified_max_upstream_pages=value)


def test_atlasdocs_env_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLASDOCS_ENV", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_development_allows_insecure_http_cookies() -> None:
    settings = Settings(
        atlasdocs_env="development",
        session_secret=DEFAULT_SESSION_SECRET,
        session_secure=False,
    )
    assert settings.cookie_secure is False


def test_session_store_evicts_when_capped(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SESSION_MAX_AGE_SECONDS", "3600")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-key")
    monkeypatch.setenv("ATLASDOCS_ENV", "development")
    get_settings.cache_clear()
    reset_engine()
    engine = get_engine(f"sqlite+pysqlite:///{tmp_path / 'sess.db'}")
    Base.metadata.create_all(engine)
    db = get_session_factory()()
    try:
        store = DbSessionStore(db, max_sessions=2)
        first = store.create()
        second = store.create()
        third = store.create()
        db.commit()
        assert store.get(first.id) is None
        assert store.get(second.id) is not None
        assert store.get(third.id) is not None
    finally:
        db.close()
        reset_engine()


@pytest.mark.parametrize("value", [0, -1])
def test_session_store_rejects_non_positive_capacity(
    tmp_path, monkeypatch: pytest.MonkeyPatch, value: int
) -> None:
    monkeypatch.setenv("ATLASDOCS_ENV", "development")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-key")
    get_settings.cache_clear()
    reset_engine()
    engine = get_engine(f"sqlite+pysqlite:///{tmp_path / 'sess.db'}")
    Base.metadata.create_all(engine)
    db = get_session_factory()()
    try:
        store = DbSessionStore(db, max_sessions=value)
        with pytest.raises(ValueError):
            store.create()
    finally:
        db.close()
        reset_engine()


def test_session_save_does_not_resurrect_deleted_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SESSION_MAX_AGE_SECONDS", "3600")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-key")
    monkeypatch.setenv("ATLASDOCS_ENV", "development")
    get_settings.cache_clear()
    reset_engine()
    engine = get_engine(f"sqlite+pysqlite:///{tmp_path / 'sess.db'}")
    Base.metadata.create_all(engine)
    db = get_session_factory()()
    try:
        store = DbSessionStore(db, max_sessions=10)
        session = store.create(paperless_authorization="Token secret")
        store.delete(session.id)
        assert store.rotate_csrf(session) is False
        assert store.get(session.id) is None
    finally:
        db.close()
        reset_engine()


def test_undecryptable_session_is_dropped(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SESSION_MAX_AGE_SECONDS", "3600")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "original-key")
    monkeypatch.setenv("ATLASDOCS_ENV", "development")
    get_settings.cache_clear()
    reset_engine()
    engine = get_engine(f"sqlite+pysqlite:///{tmp_path / 'sess.db'}")
    Base.metadata.create_all(engine)
    db = get_session_factory()()
    try:
        store = DbSessionStore(db, max_sessions=10)
        session = store.create(paperless_authorization="Token secret")
        session_id = session.id
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "rotated-key")
        get_settings.cache_clear()
        assert store.get(session_id) is None
        assert store.get(session_id) is None
    finally:
        db.close()
        reset_engine()
