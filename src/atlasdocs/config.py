from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# Unclassified inbox: one Paperless page, then a single AtlasDocs filter query.
UNCLASSIFIED_PAGE_SIZE = 25
DEFAULT_SESSION_SECRET = "dev-only-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_host: str = "db"
    database_port: int = 5432
    database_name: str = "atlasdocs"
    database_user: str = "atlasdocs"
    database_password: str = "atlasdocs"

    paperless_base_url: str = "http://localhost:8000"
    paperless_timeout_seconds: float = 10.0
    seed_path: str = "config/seed/v0.1.yaml"
    # Not used for per-user document access. Browser UI uses a server-side session;
    # JSON API requires an Authorization header on every document request.
    paperless_token: str | None = None

    atlasdocs_env: str = "development"
    session_secret: str = DEFAULT_SESSION_SECRET
    session_secure: bool = False
    session_max_age_seconds: int = 60 * 60 * 8
    session_cookie_name: str = "atlasdocs_sid"
    unclassified_page_size: int = UNCLASSIFIED_PAGE_SIZE

    @field_validator("atlasdocs_env")
    @classmethod
    def _normalize_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "production"}:
            raise ValueError("ATLASDOCS_ENV must be 'development' or 'production'")
        return normalized

    @model_validator(mode="after")
    def _validate_production_session(self) -> Settings:
        if self.atlasdocs_env == "production":
            if self.session_secret == DEFAULT_SESSION_SECRET:
                raise ValueError(
                    "SESSION_SECRET must be set to a non-default value when ATLASDOCS_ENV=production"
                )
            if not self.session_secure:
                raise ValueError(
                    "SESSION_SECURE must be true when ATLASDOCS_ENV=production"
                )
        return self

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies are required in production; optional for local HTTP."""
        if self.atlasdocs_env == "production":
            return True
        return self.session_secure

    def sqlalchemy_url(self) -> URL:
        """Build a SQLAlchemy URL without embedding credentials in env as one string."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        )

    def paperless_document_url(self, paperless_document_id: int) -> str:
        return f"{self.paperless_base_url.rstrip('/')}/documents/{paperless_document_id}/"


@lru_cache
def get_settings() -> Settings:
    return Settings()
