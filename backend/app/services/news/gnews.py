"""GNews provider (https://docs.gnews.io). Free plan: 100 requests/day, 1 request/second,
10 articles per request, ~12 hour delay, article content cut to ~250 characters."""

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.services.news.base import (
    NewsProviderError,
    NormalizedArticle,
    SearchParams,
    http_url_or_none,
)

DEFAULT_BASE_URL = "https://gnews.io/api/v4"
PAGE_SIZE = 10  # free plan maximum

_PERIODS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
_SORTS = {"relevance": "relevance", "latest": "publishedAt"}

# Free-plan content ends with e.g. "... [5836 chars]"; drop that marker.
_TRUNCATION_MARKER = re.compile(r"\s*\.\.\.\s*\[\d+ chars\]\s*$")


def clean_snippet(content: str | None) -> str | None:
    if not content:
        return None
    return _TRUNCATION_MARKER.sub("…", content).strip() or None


def normalize(raw: dict[str, Any]) -> NormalizedArticle | None:
    """Map one GNews article to ours. Returns None if its link isn't a safe http(s) URL."""
    url = http_url_or_none(raw.get("url"))
    if url is None:
        return None
    source = raw.get("source") or {}
    return NormalizedArticle(
        provider="gnews",
        provider_article_id=raw["id"],
        title=raw["title"],
        description=raw.get("description") or None,
        snippet=clean_snippet(raw.get("content")),
        url=url,
        image_url=http_url_or_none(raw.get("image")),
        source_name=source.get("name") or "Unknown source",
        source_url=http_url_or_none(source.get("url")),
        published_at=raw["publishedAt"],
    )


def _parse_errors(response: httpx.Response) -> tuple[str, dict[str, str]]:
    """GNews errors are {"errors": ["msg", ...]} for request-level problems (e.g. a missing key)
    or {"errors": {"q": "msg"}} when a specific parameter is at fault.
    Returns (combined message, per-parameter errors)."""
    try:
        errors = response.json().get("errors")
    except ValueError:
        return response.text, {}
    if isinstance(errors, dict):
        by_param = {str(k): str(v) for k, v in errors.items()}
        return " ".join(by_param.values()), by_param
    if isinstance(errors, list):
        return " ".join(str(v) for v in errors), {}
    return response.text, {}


class GNewsProvider:
    name = "gnews"

    def __init__(
        self,
        api_key: str,
        client: httpx.Client,
        base_url: str = DEFAULT_BASE_URL,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._api_key = api_key
        self._client = client
        self._base_url = base_url
        self._now = now or (lambda: datetime.now(UTC))

    def search(self, params: SearchParams) -> list[NormalizedArticle]:
        query: dict[str, str | int] = {
            "q": params.q,
            "lang": "en",
            "max": PAGE_SIZE,
            "sortby": _SORTS[params.sort],
        }
        if params.period:
            since = self._now() - _PERIODS[params.period]
            query["from"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        data = self._get("/search", query)
        articles = (normalize(raw) for raw in data.get("articles", []))
        return [a for a in articles if a is not None]

    def _get(self, path: str, query: dict[str, str | int]) -> dict[str, Any]:
        try:
            # Key goes in a header, not the URL, so it never shows up in logs.
            response = self._client.get(
                f"{self._base_url}{path}", params=query, headers={"X-Api-Key": self._api_key}
            )
        except httpx.HTTPError as exc:
            raise NewsProviderError.unavailable() from exc

        status = response.status_code
        if status == 200:
            return response.json()

        message, by_param = _parse_errors(response)
        # Decide by structure, not wording: GNews's missing-key message also mentions the
        # "apikey query parameter", so matching on "query" would blame the user's search.
        if status == 400 and "q" in by_param:
            raise NewsProviderError.invalid_query(by_param["q"])
        if status == 403 and "quota" in message.lower():
            raise NewsProviderError.quota_exceeded(
                "Today's news search quota is used up. It resets at 00:00 UTC."
            )
        if status == 429:
            raise NewsProviderError.rate_limited()
        if status in (400, 401, 403):
            raise NewsProviderError.misconfigured()
        raise NewsProviderError.unavailable()
