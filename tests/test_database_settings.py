from __future__ import annotations

import os

import pytest
from sqlalchemy.engine import URL

from atlasdocs.config import Settings, get_settings
from atlasdocs.db.session import get_engine, reset_engine


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    reset_engine()
    yield
    get_settings.cache_clear()
    reset_engine()


def test_default_split_database_settings() -> None:
    settings = Settings(atlasdocs_env="development")
    assert settings.database_host == "db"
    assert settings.database_port == 5432
    assert settings.database_name == "atlasdocs"
    assert settings.database_user == "atlasdocs"
    assert settings.database_password.get_secret_value() == "atlasdocs"

    url = settings.sqlalchemy_url()
    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg"
    assert url.host == "db"
    assert url.port == 5432
    assert url.database == "atlasdocs"
    assert url.username == "atlasdocs"
    assert url.password == "atlasdocs"


def test_split_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_HOST", "postgres.internal")
    monkeypatch.setenv("DATABASE_PORT", "6543")
    monkeypatch.setenv("DATABASE_NAME", "atlasdocs_prod")
    monkeypatch.setenv("DATABASE_USER", "atlasdocs_app")
    monkeypatch.setenv("DATABASE_PASSWORD", "secret")

    settings = Settings(atlasdocs_env="development")
    url = settings.sqlalchemy_url()
    assert url.host == "postgres.internal"
    assert url.port == 6543
    assert url.database == "atlasdocs_prod"
    assert url.username == "atlasdocs_app"
    assert url.password == "secret"


def test_password_with_special_characters_is_escaped() -> None:
    password = "p@ss:w/ord%#?&="
    settings = Settings(atlasdocs_env="development", database_password=password)
    url = settings.sqlalchemy_url()

    assert url.password == password

    rendered = url.render_as_string(hide_password=False)
    assert password not in rendered
    assert "%40" in rendered  # @
    assert "%3A" in rendered or "%3a" in rendered  # :
    assert "%2F" in rendered or "%2f" in rendered  # /
    assert "%25" in rendered  # %

    # Round-trip through SQLAlchemy URL parsing preserves the password.
    parsed = URL.create(
        drivername=url.drivername,
        username=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        database=url.database,
    )
    assert parsed.password == password


def test_get_engine_uses_split_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_HOST", "db")
    monkeypatch.setenv("DATABASE_PORT", "5432")
    monkeypatch.setenv("DATABASE_NAME", "atlasdocs")
    monkeypatch.setenv("DATABASE_USER", "atlasdocs")
    monkeypatch.setenv("DATABASE_PASSWORD", "atlasdocs")
    get_settings.cache_clear()

    engine = get_engine()
    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.host == "db"
    assert engine.url.database == "atlasdocs"
    assert "DATABASE_URL" not in os.environ


def test_get_engine_rebuilds_when_password_changes() -> None:
    first = URL.create(
        drivername="postgresql+psycopg",
        username="atlasdocs",
        password="one",
        host="db",
        port=5432,
        database="atlasdocs",
    )
    second = URL.create(
        drivername="postgresql+psycopg",
        username="atlasdocs",
        password="two",
        host="db",
        port=5432,
        database="atlasdocs",
    )
    assert str(first) == str(second)  # password is masked in str()
    engine_one = get_engine(first)
    engine_two = get_engine(second)
    assert engine_one is not engine_two
    assert engine_two.url.password == "two"
