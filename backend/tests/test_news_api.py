from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.news import get_news_provider
from app.services.news.base import NewsProviderError, NormalizedArticle, SearchParams
from app.services.news.fake import FakeNewsProvider


class RecordingProvider(FakeNewsProvider):
    """Fake provider that remembers the params it was called with."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[SearchParams] = []

    def search(self, params: SearchParams) -> list[NormalizedArticle]:
        self.calls.append(params)
        return super().search(params)


class FailingProvider:
    name = "failing"

    def search(self, params: SearchParams) -> list[NormalizedArticle]:
        raise NewsProviderError.quota_exceeded("Quota used up")


@pytest.fixture
def provider() -> Iterator[RecordingProvider]:
    fake = RecordingProvider()
    app.dependency_overrides[get_news_provider] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


client = TestClient(app)


def test_search_returns_normalized_items(provider: RecordingProvider) -> None:
    res = client.get("/api/news/search", params={"q": "anthropic"})

    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "fake"
    assert body["query"] == "anthropic"
    assert body["items"]
    assert set(body["items"][0]) >= {"title", "url", "image_url", "source_name", "published_at"}


def test_search_passes_trimmed_query_sort_and_period(provider: RecordingProvider) -> None:
    client.get("/api/news/search", params={"q": "  ai chips ", "sort": "relevance", "period": "7d"})

    assert provider.calls == [SearchParams(q="ai chips", sort="relevance", period="7d")]


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"q": ""},
        {"q": "   "},
        {"q": "x" * 201},
        {"q": "ai", "sort": "popularity"},
        {"q": "ai", "period": "1y"},
    ],
)
def test_invalid_input_is_422(provider: RecordingProvider, params: dict[str, str]) -> None:
    res = client.get("/api/news/search", params=params)

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"
    assert provider.calls == []


def test_provider_errors_use_error_envelope() -> None:
    app.dependency_overrides[get_news_provider] = FailingProvider
    try:
        res = client.get("/api/news/search", params={"q": "ai"})
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 429
    assert res.json()["error"]["code"] == "news_quota_exceeded"
