from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment variables (and backend/.env locally)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"

    # "fake" serves a saved response and uses no API quota; "gnews" calls the real API.
    news_provider: Literal["gnews", "fake"] = "fake"
    gnews_api_key: SecretStr | None = None
    # Real provider calls allowed per UTC day; GNews free is 100, so keep a small margin.
    news_daily_request_limit: int = 95

    # Local default: the docker-compose Postgres (port 5433). Railway injects DATABASE_URL.
    database_url: str = "postgresql+psycopg://app:app@localhost:5433/news_analyser"

    # Built frontend (Vite's dist/). Set in Docker so FastAPI serves the app; unset in dev,
    # where Vite serves it instead.
    static_dir: Path | None = None

    # Sign-in for the deployed app: one shared password. Off when APP_PASSWORD is unset.
    # SESSION_SECRET signs the session cookie; required whenever APP_PASSWORD is set.
    app_password: SecretStr | None = None
    session_secret: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Railway gives postgresql://... (and some hosts postgres://...); SQLAlchemy needs
        the driver named explicitly to use psycopg 3."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    @field_validator("static_dir", "app_password", "session_secret", mode="before")
    @classmethod
    def blank_is_unset(cls, value: object) -> object:
        """`.env.example` ships empty values (VAR=), which should mean "not set"."""
        return None if isinstance(value, str) and not value.strip() else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
