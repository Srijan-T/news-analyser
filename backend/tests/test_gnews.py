import json
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

from app.services.news.base import NewsProviderError, SearchParams
from app.services.news.fake import FIXTURE
from app.services.news.gnews import GNewsProvider, clean_snippet

FIXED_NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
Handler = Callable[[httpx.Request], httpx.Response]


def make_provider(handler: Handler) -> GNewsProvider:
    """GNewsProvider wired to a fake transport: no network, and we can inspect each request."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GNewsProvider(api_key="test-key", client=client, now=lambda: FIXED_NOW)


def fixture_response(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=json.loads(FIXTURE.read_text()))


def error_response(status: int, errors: object) -> Handler:
    return lambda _: httpx.Response(status, json={"errors": errors})


def test_search_normalizes_articles() -> None:
    articles = make_provider(fixture_response).search(SearchParams(q="openai"))

    assert len(articles) == 10
    first = articles[0]
    assert first.provider == "gnews"
    assert first.title and first.url.startswith("http")
    assert first.source_name == "Business Today"
    assert first.published_at.tzinfo is not None
    assert first.snippet is not None and "chars]" not in first.snippet


def test_search_sends_expected_params_and_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"totalArticles": 0, "articles": []})

    make_provider(handler).search(SearchParams(q="climate policy", sort="relevance", period="24h"))

    request = seen[0]
    assert request.url.path == "/api/v4/search"
    assert dict(request.url.params) == {
        "q": "climate policy",
        "lang": "en",
        "max": "10",
        "sortby": "relevance",
        "from": "2026-11-18T12:00:00Z",
    }
    assert request.headers["X-Api-Key"] == "test-key"
    assert "apikey" not in str(request.url)  # key must never be in the URL


def test_latest_sort_maps_to_published_at_and_no_period_sends_no_from() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"articles": []})

    make_provider(handler).search(SearchParams(q="ai"))

    assert seen[0].url.params["sortby"] == "publishedAt"
    assert "from" not in seen[0].url.params


@pytest.mark.parametrize(
    ("status", "errors", "expected_status", "expected_code"),
    [
        (400, {"q": "The query has a syntax error."}, 400, "invalid_query"),
        # Real GNews wording: it mentions the "apikey query parameter", which must not be
        # mistaken for a query-syntax error.
        (
            400,
            [
                "The request has no API key. Send your API key in the apikey query parameter "
                "or the X-Api-Key header."
            ],
            502,
            "news_provider_misconfigured",
        ),
        (401, ["The API key doesn't match any account."], 502, "news_provider_misconfigured"),
        (403, ["Your daily quota of 100 requests is used up."], 429, "news_quota_exceeded"),
        (403, ["Verify your email address."], 502, "news_provider_misconfigured"),
        (429, ["You sent too many requests per second."], 429, "news_rate_limited"),
        (503, ["Service unavailable."], 502, "news_provider_unavailable"),
    ],
)
def test_provider_errors_map_to_client_errors(
    status: int, errors: object, expected_status: int, expected_code: str
) -> None:
    provider = make_provider(error_response(status, errors))

    with pytest.raises(NewsProviderError) as exc_info:
        provider.search(SearchParams(q="ai"))

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.code == expected_code


def test_network_failure_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    with pytest.raises(NewsProviderError) as exc_info:
        make_provider(handler).search(SearchParams(q="ai"))

    assert exc_info.value.code == "news_provider_unavailable"


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("Some text that was cut... [5836 chars]", "Some text that was cut…"),
        ("Complete short text.", "Complete short text."),
        (None, None),
        ("", None),
    ],
)
def test_clean_snippet(content: str | None, expected: str | None) -> None:
    assert clean_snippet(content) == expected


def _raw_article(**overrides: object) -> dict[str, object]:
    article: dict[str, object] = {
        "id": "a1",
        "title": "Title",
        "description": "Desc",
        "content": "Body",
        "url": "https://example.com/story",
        "image": "https://example.com/img.jpg",
        "publishedAt": "2026-11-19T10:00:00Z",
        "source": {"name": "Example", "url": "https://example.com"},
    }
    return article | overrides


def test_articles_with_non_http_urls_are_dropped() -> None:
    articles = [
        _raw_article(id="ok"),
        _raw_article(id="js", url="javascript:alert(document.cookie)"),
        _raw_article(id="data", url="data:text/html,<script>alert(1)</script>"),
    ]
    provider = make_provider(lambda _: httpx.Response(200, json={"articles": articles}))

    results = provider.search(SearchParams(q="ai"))

    assert [a.provider_article_id for a in results] == ["ok"]


def test_non_http_image_and_source_urls_are_cleared() -> None:
    raw = _raw_article(image="javascript:alert(1)", source={"name": "X", "url": "ftp://x"})
    provider = make_provider(lambda _: httpx.Response(200, json={"articles": [raw]}))

    [article] = provider.search(SearchParams(q="ai"))

    assert article.image_url is None
    assert article.source_url is None
