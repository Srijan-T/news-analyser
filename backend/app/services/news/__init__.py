from functools import lru_cache

import httpx

from app.config import get_settings
from app.errors import AppError
from app.services.news.base import NewsProvider
from app.services.news.fake import FakeNewsProvider
from app.services.news.gnews import GNewsProvider


@lru_cache
def get_news_provider() -> NewsProvider:
    """FastAPI dependency: the provider picked by NEWS_PROVIDER. Tests override this."""
    settings = get_settings()
    if settings.news_provider == "fake":
        return FakeNewsProvider()
    api_key = settings.gnews_api_key.get_secret_value().strip() if settings.gnews_api_key else ""
    if not api_key:  # .env.example ships GNEWS_API_KEY= (empty), so treat blank as missing
        raise AppError(
            500, "news_provider_not_configured", "NEWS_PROVIDER=gnews but GNEWS_API_KEY is not set"
        )
    return GNewsProvider(
        api_key=api_key,
        client=httpx.Client(timeout=10.0),
    )
