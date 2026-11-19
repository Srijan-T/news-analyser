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

    # Built frontend (Vite's dist/). Set in Docker so FastAPI serves the app; unset in dev,
    # where Vite serves it instead.
    static_dir: Path | None = None

    # HTTP basic auth for the deployed app. Off unless both are set.
    basic_auth_user: str | None = None
    basic_auth_password: SecretStr | None = None

    @field_validator("static_dir", "basic_auth_user", "basic_auth_password", mode="before")
    @classmethod
    def blank_is_unset(cls, value: object) -> object:
        """`.env.example` ships empty values (VAR=), which should mean "not set"."""
        return None if isinstance(value, str) and not value.strip() else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
