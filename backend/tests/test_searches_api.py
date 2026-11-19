from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.main import create_app
from app.models import Article, Search
from app.services.news import get_news_provider
from app.services.news.base import NewsProviderError, NormalizedArticle, SearchParams
from app.services.news.fake import FakeNewsProvider


class RecordingProvider(FakeNewsProvider):
    """Fake provider that counts real calls (so we can see cache hits) and can pretend to be
    another provider (the quota guard only applies to real ones)."""

    def __init__(self, name: str = "fake") -> None:
        super().__init__()
        self.name = name
        self.calls: list[SearchParams] = []

    def search(self, params: SearchParams) -> list[NormalizedArticle]:
        self.calls.append(params)
        return super().search(params)


class FailingProvider:
    name = "gnews"

    def search(self, params: SearchParams) -> list[NormalizedArticle]:
        raise NewsProviderError.unavailable()


MakeClient = Callable[..., TestClient]


@pytest.fixture
def make_client(db: Session) -> MakeClient:
    def make(provider: object, **settings: object) -> TestClient:
        app = create_app(Settings.model_validate(settings))
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_news_provider] = lambda: provider
        return TestClient(app)

    return make


@pytest.fixture
def provider() -> RecordingProvider:
    return RecordingProvider()


@pytest.fixture
def client(make_client: MakeClient, provider: RecordingProvider) -> TestClient:
    return make_client(provider)


def search(client: TestClient, q: str = "anthropic", **params: str):
    return client.post("/api/searches", json={"q": q, **params})


# --- creating and caching -----------------------------------------------------------------


def test_new_search_is_stored_and_returns_201(client: TestClient, db: Session) -> None:
    res = search(client, sort="latest", period="7d")

    assert res.status_code == 201
    body = res.json()
    assert body["query"] == "anthropic"
    assert body["sort"] == "latest"
    assert body["period"] == "7d"
    assert body["provider"] == "fake"
    assert body["result_count"] == len(body["items"]) > 0
    assert all(isinstance(item["id"], int) for item in body["items"])
    assert db.scalar(select(func.count()).select_from(Search)) == 1


def test_repeat_search_within_30_minutes_is_served_from_cache(
    client: TestClient, provider: RecordingProvider
) -> None:
    first = search(client, "Anthropic")
    second = search(client, "  anthropic  ")  # same search after normalizing case/space

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(provider.calls) == 1  # no second provider call, no quota spent


def test_different_sort_or_period_is_a_different_search(
    client: TestClient, provider: RecordingProvider
) -> None:
    search(client, sort="latest")
    search(client, sort="relevance")
    search(client, sort="relevance", period="24h")

    assert len(provider.calls) == 3


def test_expired_cache_calls_the_provider_again(
    client: TestClient, provider: RecordingProvider, db: Session
) -> None:
    first = search(client).json()
    db.execute(
        update(Search)
        .where(Search.id == first["id"])
        .values(created_at=datetime.now(UTC) - timedelta(minutes=31))
    )

    second = search(client)

    assert second.status_code == 201
    assert second.json()["id"] != first["id"]
    assert len(provider.calls) == 2


def test_articles_are_stored_once_across_searches(client: TestClient, db: Session) -> None:
    by_latest = search(client, "openai", sort="latest").json()
    by_relevance = search(client, "openai", sort="relevance").json()

    assert {a["url"]: a["id"] for a in by_latest["items"]} == {
        a["url"]: a["id"] for a in by_relevance["items"]
    }
    assert db.scalar(select(func.count()).select_from(Article)) == len(by_latest["items"])


def test_provider_failure_stores_nothing(make_client: MakeClient, db: Session) -> None:
    res = search(make_client(FailingProvider()))

    assert res.status_code == 502
    assert db.scalar(select(func.count()).select_from(Search)) == 0


@pytest.mark.parametrize(
    "body",
    [{}, {"q": ""}, {"q": "   "}, {"q": "x" * 201}, {"q": "ai", "sort": "popularity"}],
)
def test_invalid_search_is_422_and_calls_nothing(
    client: TestClient, provider: RecordingProvider, body: dict[str, str]
) -> None:
    res = client.post("/api/searches", json=body)

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"
    assert provider.calls == []


# --- reading ------------------------------------------------------------------------------


def test_get_search_returns_stored_results_in_order(
    client: TestClient, provider: RecordingProvider
) -> None:
    created = search(client, sort="latest").json()

    res = client.get(f"/api/searches/{created['id']}")

    assert res.status_code == 200
    assert [a["url"] for a in res.json()["items"]] == [a["url"] for a in created["items"]]
    assert len(provider.calls) == 1  # reading never calls the provider


def test_unknown_search_is_404(client: TestClient) -> None:
    res = client.get("/api/searches/999999")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "search_not_found"


def test_search_history_is_newest_first_and_paginated(client: TestClient) -> None:
    ids = [search(client, q).json()["id"] for q in ("alpha", "beta", "gamma")]

    page = client.get("/api/searches", params={"limit": 2, "offset": 0}).json()

    assert page["total"] == 3
    assert page["limit"] == 2
    assert page["offset"] == 0
    assert [s["id"] for s in page["items"]] == [ids[2], ids[1]]
    assert set(page["items"][0]) >= {"id", "query", "sort", "period", "result_count", "created_at"}
    assert "items" not in page["items"][0]  # summaries only, no article lists


# --- daily quota --------------------------------------------------------------------------


def test_quota_blocks_new_searches_but_not_cached_ones(make_client: MakeClient) -> None:
    provider = RecordingProvider(name="gnews")
    client = make_client(provider, news_daily_request_limit=2)

    search(client, "alpha")
    search(client, "beta")
    blocked = search(client, "gamma")
    cached = search(client, "alpha")

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "news_quota_exceeded"
    assert cached.status_code == 200
    assert len(provider.calls) == 2


def test_quota_endpoint_reports_usage(make_client: MakeClient) -> None:
    client = make_client(RecordingProvider(name="gnews"), news_daily_request_limit=95)
    search(client, "alpha")
    search(client, "alpha")  # cached: not counted

    assert client.get("/api/quota").json() == {
        "provider": "gnews",
        "limit": 95,
        "used": 1,
        "remaining": 94,
    }


def test_yesterdays_searches_dont_count(make_client: MakeClient, db: Session) -> None:
    client = make_client(RecordingProvider(name="gnews"), news_daily_request_limit=95)
    created = search(client, "alpha").json()
    db.execute(
        update(Search)
        .where(Search.id == created["id"])
        .values(created_at=datetime.now(UTC) - timedelta(days=1, hours=1))
    )

    assert client.get("/api/quota").json()["used"] == 0


def test_fake_provider_has_no_quota(client: TestClient) -> None:
    assert client.get("/api/quota").json() == {
        "provider": "fake",
        "limit": None,
        "used": 0,
        "remaining": None,
    }


# --- review fixes -------------------------------------------------------------------------


class DuplicatingProvider(FakeNewsProvider):
    """Returns the first article twice, as a provider occasionally does."""

    def search(self, params: SearchParams) -> list[NormalizedArticle]:
        articles = super().search(params)
        return [articles[0], *articles]


def test_duplicate_urls_from_provider_are_stored_once(make_client: MakeClient) -> None:
    client = make_client(DuplicatingProvider())

    res = search(client, "openai")

    assert res.status_code == 201
    urls = [a["url"] for a in res.json()["items"]]
    assert len(urls) == len(set(urls))
    assert res.json()["result_count"] == len(urls)


def test_dedupe_keeps_first_occurrence_in_provider_order() -> None:
    from app.services.searches import _dedupe_by_url

    a, b, c = FakeNewsProvider().search(SearchParams(q="zzz-no-match"))[:3]
    assert [x.url for x in _dedupe_by_url([a, b, a, c])] == [a.url, b.url, c.url]


# --- quota counts provider requests, not rows ---------------------------------------------


def test_quota_counts_every_provider_request_a_search_made(
    make_client: MakeClient, db: Session
) -> None:
    client = make_client(RecordingProvider(name="gnews"), news_daily_request_limit=95)
    db.add(
        Search(
            provider="gnews",
            query="environmental improvements",
            sort="latest",
            period=None,
            cache_key="k",
            result_count=4,
            provider_requests=3,  # exact + corrected + broadened
        )
    )
    db.flush()

    assert client.get("/api/quota").json()["used"] == 3
