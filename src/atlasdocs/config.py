from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# Unclassified inbox: bounded Paperless pages, then one AtlasDocs filter per page.
UNCLASSIFIED_PAGE_SIZE = 25
UNCLASSIFIED_MAX_UPSTREAM_PAGES = 5
DEFAULT_SESSION_SECRET = "dev-only-change-me"
DEFAULT_DATABASE_PASSWORD = "atlasdocs"
MAX_UI_SESSIONS = 1000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_host: str = "db"
    database_port: int = 5432
    database_name: str = "atlasdocs"
    database_user: str = "atlasdocs"
    database_password: SecretStr = SecretStr(DEFAULT_DATABASE_PASSWORD)

    paperless_base_url: str = "http://localhost:8000"
    paperless_timeout_seconds: float = 10.0
    seed_path: str = "config/seed/v0.1.yaml"

    # Required. Do not default to development — omit means misconfigured deploy.
    atlasdocs_env: str
    session_secret: str = DEFAULT_SESSION_SECRET
    session_secure: bool = False
    session_max_age_seconds: int = 60 * 60 * 8
    session_cookie_name: str = "atlasdocs_sid"
    unclassified_page_size: int = UNCLASSIFIED_PAGE_SIZE
    unclassified_max_upstream_pages: int = UNCLASSIFIED_MAX_UPSTREAM_PAGES

    @field_validator("atlasdocs_env")
    @classmethod
    def _normalize_env(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in {"development", "production"}:
            raise ValueError("ATLASDOCS_ENV is required and must be 'development' or 'production'")
        return normalized

    @field_validator("session_secret")
    @classmethod
    def _strip_session_secret(cls, value: str) -> str:
        return value.strip()

    @field_validator("unclassified_max_upstream_pages")
    @classmethod
    def _positive_upstream_pages(cls, value: int) -> int:
        if value < 1:
            raise ValueError("UNCLASSIFIED_MAX_UPSTREAM_PAGES must be >= 1")
        return value

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> Settings:
        if self.atlasdocs_env == "production":
            if not self.session_secret or self.session_secret == DEFAULT_SESSION_SECRET:
                raise ValueError(
                    "SESSION_SECRET must be a non-empty, non-default value when "
                    "ATLASDOCS_ENV=production"
                )
            if not self.session_secure:
                raise ValueError(
                    "SESSION_SECURE must be true when ATLASDOCS_ENV=production"
                )
            password = self.database_password.get_secret_value()
            if not password or password == DEFAULT_DATABASE_PASSWORD:
                raise ValueError(
                    "DATABASE_PASSWORD must be a non-empty, non-default value when "
                    "ATLASDOCS_ENV=production"
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
            password=self.database_password.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        )

    def paperless_document_url(self, paperless_document_id: int) -> str:
        return f"{self.paperless_base_url.rstrip('/')}/documents/{paperless_document_id}/"


@lru_cache
def get_settings() -> Settings:
    return Settings()
