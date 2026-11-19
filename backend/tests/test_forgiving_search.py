"""Zero-result searches retry with a corrected query, then with "match any word"."""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.main import create_app
from app.models import Search
from app.services.news import get_news_provider
from app.services.news.base import NewsProviderError, NormalizedArticle, SearchParams
from app.services.query_fix import get_query_corrector
from app.services.searches import broaden

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def article(n: int) -> NormalizedArticle:
    return NormalizedArticle(
        provider="gnews",
        provider_article_id=f"a{n}",
        title=f"Article {n}",
        description=None,
        snippet=None,
        url=f"https://example.com/{n}",
        image_url=None,
        source_name="Example",
        source_url=None,
        published_at=NOW,
    )


class ScriptedProvider:
    """Returns canned results per exact query string; records every call."""

    name = "gnews"

    def __init__(self, results: dict[str, int], fail_on: str | None = None) -> None:
        self.results = results
        self.fail_on = fail_on
        self.calls: list[str] = []

    def search(self, params: SearchParams) -> list[NormalizedArticle]:
        self.calls.append(params.q)
        if params.q == self.fail_on:
            raise NewsProviderError.unavailable()
        return [article(n) for n in range(self.results.get(params.q, 0))]


class StubCorrector:
    def __init__(self, fixes: dict[str, str]) -> None:
        self.fixes = fixes
        self.calls: list[str] = []

    def suggest(self, query: str) -> str | None:
        self.calls.append(query)
        return self.fixes.get(query)


TYPO = "environmental improvemenets"
FIXED = "environmental improvements"
BROAD = "environmental OR improvements"

MakeClient = Callable[..., TestClient]


@pytest.fixture
def make_client(db: Session) -> MakeClient:
    def make(provider: object, corrector: object, **settings: object) -> TestClient:
        app = create_app(Settings.model_validate({"news_min_request_interval": 0} | settings))
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_news_provider] = lambda: provider
        app.dependency_overrides[get_query_corrector] = lambda: corrector
        return TestClient(app)

    return make


def post(client: TestClient, q: str, **extra: object):
    return client.post("/api/searches", json={"q": q, **extra})


def test_search_with_results_never_tries_fallbacks(make_client: MakeClient) -> None:
    provider, corrector = ScriptedProvider({TYPO: 3}), StubCorrector({TYPO: FIXED})
    body = post(make_client(provider, corrector), TYPO).json()

    assert provider.calls == [TYPO]
    assert corrector.calls == []
    assert (body["query"], body["original_query"], body["match_mode"]) == (TYPO, None, "all")


def test_zero_results_retry_with_the_corrected_query(make_client: MakeClient, db: Session) -> None:
    provider = ScriptedProvider({FIXED: 4})
    body = post(make_client(provider, StubCorrector({TYPO: FIXED})), TYPO).json()

    assert provider.calls == [TYPO, FIXED]
    assert body["query"] == FIXED
    assert body["original_query"] == TYPO
    assert body["match_mode"] == "all"
    assert body["result_count"] == 4
    assert db.scalars(select(Search)).one().provider_requests == 2


def test_still_nothing_broadens_to_any_word(make_client: MakeClient, db: Session) -> None:
    provider = ScriptedProvider({BROAD: 5})
    body = post(make_client(provider, StubCorrector({TYPO: FIXED})), TYPO).json()

    assert provider.calls == [TYPO, FIXED, BROAD]
    assert (body["query"], body["original_query"], body["match_mode"]) == (BROAD, TYPO, "any")
    assert db.scalars(select(Search)).one().provider_requests == 3


def test_no_correction_goes_straight_to_broadening(make_client: MakeClient) -> None:
    provider = ScriptedProvider({"rare OR topic": 2})
    body = post(make_client(provider, StubCorrector({})), "rare topic").json()

    assert provider.calls == ["rare topic", "rare OR topic"]
    assert body["match_mode"] == "any"


def test_never_more_than_three_provider_calls(make_client: MakeClient) -> None:
    provider = ScriptedProvider({})
    body = post(make_client(provider, StubCorrector({TYPO: FIXED})), TYPO).json()

    assert len(provider.calls) == 3
    assert body["result_count"] == 0
    # Nothing found anywhere: report the search as typed, not a fallback that also failed.
    assert (body["query"], body["original_query"], body["match_mode"]) == (TYPO, None, "all")


def test_exact_flag_skips_all_fallbacks(make_client: MakeClient) -> None:
    provider, corrector = ScriptedProvider({FIXED: 4}), StubCorrector({TYPO: FIXED})
    body = post(make_client(provider, corrector), TYPO, exact=True).json()

    assert provider.calls == [TYPO]
    assert corrector.calls == []
    assert body["result_count"] == 0


def test_exact_and_forgiving_searches_are_cached_separately(make_client: MakeClient) -> None:
    provider = ScriptedProvider({FIXED: 4})
    client = make_client(provider, StubCorrector({TYPO: FIXED}))

    forgiving = post(client, TYPO).json()
    exact = post(client, TYPO, exact=True).json()

    assert forgiving["id"] != exact["id"]
    assert exact["result_count"] == 0


def test_repeating_a_typo_is_served_from_cache(make_client: MakeClient) -> None:
    provider = ScriptedProvider({FIXED: 4})
    client = make_client(provider, StubCorrector({TYPO: FIXED}))
    first = post(client, TYPO)
    second = post(client, TYPO)

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert provider.calls == [TYPO, FIXED]  # no new calls


def test_fallback_calls_count_against_the_daily_quota(make_client: MakeClient) -> None:
    client = make_client(
        ScriptedProvider({BROAD: 5}), StubCorrector({TYPO: FIXED}), news_daily_request_limit=95
    )
    post(client, TYPO)

    assert client.get("/api/quota").json()["used"] == 3


def test_fallbacks_stop_when_the_quota_runs_out(make_client: MakeClient) -> None:
    provider = ScriptedProvider({BROAD: 5})
    client = make_client(provider, StubCorrector({TYPO: FIXED}), news_daily_request_limit=2)
    res = post(client, TYPO)

    assert res.status_code == 201  # the first call succeeded: return what we have, no 429
    assert provider.calls == [TYPO, FIXED]  # the third call would exceed the limit


def test_a_failing_fallback_keeps_the_best_result_so_far(make_client: MakeClient) -> None:
    provider = ScriptedProvider({}, fail_on=FIXED)
    res = post(make_client(provider, StubCorrector({TYPO: FIXED})), TYPO)

    assert res.status_code == 201
    assert res.json()["result_count"] == 0
    assert provider.calls == [TYPO, FIXED]


def test_history_lists_the_query_that_ran(make_client: MakeClient) -> None:
    client = make_client(ScriptedProvider({FIXED: 4}), StubCorrector({TYPO: FIXED}))
    post(client, TYPO)

    assert [s["query"] for s in client.get("/api/searches").json()["items"]] == [FIXED]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("environmental improvements", "environmental OR improvements"),
        ("climate", None),  # one word: nothing to broaden
        ("ai-chips market", '"ai-chips" OR market'),  # non-alphanumeric tokens are quoted
        ("apple OR banana", None),  # already "any word"
    ],
)
def test_broaden(query: str, expected: str | None) -> None:
    assert broaden(query) == expected
