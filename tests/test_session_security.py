import pytest
from pydantic import ValidationError

from atlasdocs.config import DEFAULT_SESSION_SECRET, Settings, get_settings


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
        )


def test_production_rejects_blank_session_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            atlasdocs_env="production",
            session_secret="   ",
            session_secure=True,
        )


def test_production_requires_secure_cookies() -> None:
    with pytest.raises(ValidationError):
        Settings(
            atlasdocs_env="production",
            session_secret="production-secret",
            session_secure=False,
        )


def test_production_cookie_secure_forced() -> None:
    settings = Settings(
        atlasdocs_env="production",
        session_secret="production-secret",
        session_secure=True,
    )
    assert settings.cookie_secure is True


def test_rejects_non_positive_unclassified_max_upstream_pages() -> None:
    with pytest.raises(ValidationError):
        Settings(unclassified_max_upstream_pages=0)


def test_development_allows_insecure_http_cookies() -> None:
    settings = Settings(
        atlasdocs_env="development",
        session_secret=DEFAULT_SESSION_SECRET,
        session_secure=False,
    )
    assert settings.cookie_secure is False


def test_session_store_evicts_when_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    from atlasdocs.ui.sessions import InMemorySessionStore

    monkeypatch.setenv("SESSION_MAX_AGE_SECONDS", "3600")
    get_settings.cache_clear()
    store = InMemorySessionStore(max_sessions=2)
    first = store.create()
    second = store.create()
    third = store.create()
    assert store.get(first.id) is None
    assert store.get(second.id) is not None
    assert store.get(third.id) is not None


def test_session_store_rejects_non_positive_capacity() -> None:
    from atlasdocs.ui.sessions import InMemorySessionStore

    with pytest.raises(ValueError):
        InMemorySessionStore(max_sessions=0)


def test_session_save_does_not_resurrect_deleted_session(monkeypatch: pytest.MonkeyPatch) -> None:
    from atlasdocs.ui.sessions import InMemorySessionStore

    monkeypatch.setenv("SESSION_MAX_AGE_SECONDS", "3600")
    get_settings.cache_clear()
    store = InMemorySessionStore(max_sessions=10)
    session = store.create(paperless_authorization="Token secret")
    store.delete(session.id)
    assert store.rotate_csrf(session) is False
    assert store.get(session.id) is None
