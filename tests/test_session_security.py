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


def test_development_allows_insecure_http_cookies() -> None:
    settings = Settings(
        atlasdocs_env="development",
        session_secret=DEFAULT_SESSION_SECRET,
        session_secure=False,
    )
    assert settings.cookie_secure is False
