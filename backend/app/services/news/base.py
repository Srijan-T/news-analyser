"""Our own news model and the interface every news source implements.

Routes only ever see `NormalizedArticle`, never a provider's raw JSON, so swapping or adding
a provider means writing one new class, not touching the API or the frontend.
"""

from datetime import datetime
from typing import Literal, Protocol
from urllib.parse import urlparse

from pydantic import BaseModel

from app.errors import AppError

SortOrder = Literal["relevance", "latest"]
Period = Literal["24h", "7d", "30d"]


class SearchParams(BaseModel):
    q: str
    sort: SortOrder = "latest"
    period: Period | None = None


def http_url_or_none(value: object) -> str | None:
    """Return the URL only if it is http(s). Provider data is untrusted, and the frontend puts
    these URLs in href/src, so a `javascript:` or `data:` URL here would be an XSS vector."""
    if not isinstance(value, str):
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return value.strip()
    return None


class NormalizedArticle(BaseModel):
    provider: str
    provider_article_id: str
    title: str
    description: str | None
    snippet: str | None  # start of the article body; truncated on free news tiers
    url: str
    image_url: str | None
    source_name: str
    source_url: str | None
    published_at: datetime


class NewsProvider(Protocol):
    name: str

    def search(self, params: SearchParams) -> list[NormalizedArticle]: ...


class NewsProviderError(AppError):
    """A news provider failed in a way the client should be told about."""

    @classmethod
    def invalid_query(cls, message: str) -> "NewsProviderError":
        return cls(400, "invalid_query", message)

    @classmethod
    def quota_exceeded(cls, message: str) -> "NewsProviderError":
        return cls(429, "news_quota_exceeded", message)

    @classmethod
    def rate_limited(cls) -> "NewsProviderError":
        return cls(429, "news_rate_limited", "Too many searches at once. Wait a second and retry.")

    @classmethod
    def misconfigured(cls) -> "NewsProviderError":
        return cls(
            502, "news_provider_misconfigured", "The news provider rejected our credentials."
        )

    @classmethod
    def unavailable(cls) -> "NewsProviderError":
        return cls(502, "news_provider_unavailable", "The news provider is unavailable. Try again.")
