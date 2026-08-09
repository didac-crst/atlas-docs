from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

from atlasdocs.security.tokens import DEFAULT_TOKEN_ENCRYPTION_KEY

# Unclassified inbox: bounded Paperless pages, then one AtlasDocs filter per page.
UNCLASSIFIED_PAGE_SIZE = 25
UNCLASSIFIED_MAX_UPSTREAM_PAGES = 5
DEFAULT_SESSION_SECRET = "dev-only-change-me"
DEFAULT_DATABASE_PASSWORD = "atlasdocs"
MAX_UI_SESSIONS = 1000
DEFAULT_INGEST_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DEFAULT_INGEST_MAX_ATTEMPTS = 3
DEFAULT_INGEST_PROCESSING_TIMEOUT_SECONDS = 1800
DEFAULT_INGEST_BULK_MAX_DOCUMENTS = 50
DEFAULT_LOGIN_RATE_LIMIT_ATTEMPTS = 10
DEFAULT_LOGIN_RATE_LIMIT_WINDOW_SECONDS = 600
DEFAULT_INGEST_LEASE_SECONDS = 120
DEFAULT_INGEST_RESOLUTION_TIMEOUT_SECONDS = 900
DEFAULT_INGEST_RESOLUTION_MAX_ATTEMPTS = 30


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_host: str = "db"
    database_port: int = 5432
    database_name: str = "atlasdocs"
    database_user: str = "atlasdocs"
    database_password: SecretStr = SecretStr(DEFAULT_DATABASE_PASSWORD)

    paperless_base_url: str = "http://localhost:8000"
    # Browser-facing Paperless origin for "Open in Paperless" links. Never use
    # paperless_base_url (often an internal Docker hostname) for browser links.
    paperless_public_url: str | None = None
    paperless_timeout_seconds: float = 10.0
    seed_path: str = "config/seed/v0.1.yaml"

    # Required. Do not default to development — omit means misconfigured deploy.
    atlasdocs_env: str
    session_secret: str = DEFAULT_SESSION_SECRET
    session_secure: bool = False
    session_max_age_seconds: int = 60 * 60 * 8
    session_cookie_name: str = "atlasdocs_sid"
    token_encryption_key: str = DEFAULT_TOKEN_ENCRYPTION_KEY
    unclassified_page_size: int = UNCLASSIFIED_PAGE_SIZE
    unclassified_max_upstream_pages: int = UNCLASSIFIED_MAX_UPSTREAM_PAGES
    ingest_max_upload_bytes: int = DEFAULT_INGEST_MAX_UPLOAD_BYTES
    ingest_max_attempts: int = DEFAULT_INGEST_MAX_ATTEMPTS
    ingest_processing_timeout_seconds: int = DEFAULT_INGEST_PROCESSING_TIMEOUT_SECONDS
    ingest_bulk_max_documents: int = DEFAULT_INGEST_BULK_MAX_DOCUMENTS
    ingest_lease_seconds: int = DEFAULT_INGEST_LEASE_SECONDS
    ingest_resolution_timeout_seconds: int = DEFAULT_INGEST_RESOLUTION_TIMEOUT_SECONDS
    ingest_resolution_max_attempts: int = DEFAULT_INGEST_RESOLUTION_MAX_ATTEMPTS
    login_rate_limit_attempts: int = DEFAULT_LOGIN_RATE_LIMIT_ATTEMPTS
    login_rate_limit_window_seconds: int = DEFAULT_LOGIN_RATE_LIMIT_WINDOW_SECONDS

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

    @field_validator("paperless_public_url", mode="before")
    @classmethod
    def _empty_public_url_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("paperless_public_url")
    @classmethod
    def _normalize_public_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().rstrip("/")
        from urllib.parse import urlsplit

        parts = urlsplit(cleaned)
        if parts.scheme not in {"http", "https"}:
            raise ValueError("PAPERLESS_PUBLIC_URL must be an http(s) URL")
        if parts.username is not None or parts.password is not None:
            raise ValueError("PAPERLESS_PUBLIC_URL must not include credentials")
        if not parts.netloc:
            raise ValueError("PAPERLESS_PUBLIC_URL must include a host")
        # Rebuild without query/fragment/credentials.
        return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/")

    @field_validator("token_encryption_key")
    @classmethod
    def _strip_token_key(cls, value: str) -> str:
        return value.strip()

    @field_validator("unclassified_max_upstream_pages")
    @classmethod
    def _positive_upstream_pages(cls, value: int) -> int:
        if value < 1:
            raise ValueError("UNCLASSIFIED_MAX_UPSTREAM_PAGES must be >= 1")
        return value

    @field_validator(
        "ingest_max_upload_bytes",
        "ingest_max_attempts",
        "ingest_bulk_max_documents",
        "ingest_resolution_timeout_seconds",
        "ingest_resolution_max_attempts",
    )
    @classmethod
    def _positive_ingest_ints(cls, value: int) -> int:
        if value < 1:
            raise ValueError("ingest limits must be >= 1")
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
            if (
                not self.token_encryption_key
                or self.token_encryption_key == DEFAULT_TOKEN_ENCRYPTION_KEY
            ):
                raise ValueError(
                    "TOKEN_ENCRYPTION_KEY must be a non-empty, non-default value when "
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

    def paperless_document_url(self, paperless_document_id: int) -> str | None:
        """Browser link to the Paperless document detail page.

        Uses PAPERLESS_PUBLIC_URL only. Returns None when unset so the UI can
        hide/disable the action. Never falls back to PAPERLESS_BASE_URL.
        """
        if not self.paperless_public_url:
            return None
        return f"{self.paperless_public_url}/documents/{paperless_document_id}/"


@lru_cache
def get_settings() -> Settings:
    return Settings()
