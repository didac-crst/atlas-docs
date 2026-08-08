from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://atlasdocs:atlasdocs@localhost:5432/atlasdocs"
    paperless_base_url: str = "http://localhost:8000"
    paperless_timeout_seconds: float = 10.0
    seed_path: str = "config/seed/v0.1.yaml"
    # Optional service-level Paperless token when the request has none.
    paperless_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
