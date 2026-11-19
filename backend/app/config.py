from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment variables (and backend/.env locally)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"

    # "fake" serves a saved response and uses no API quota; "gnews" calls the real API.
    news_provider: Literal["gnews", "fake"] = "fake"
    gnews_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
