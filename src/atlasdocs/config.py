from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


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
    # Optional service-level Paperless token when the request has none.
    paperless_token: str | None = None

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
