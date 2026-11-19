from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.main import create_app
from app.models import Analysis, Article, Search, SearchResult

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)


@pytest.fixture
def client(db: Session) -> TestClient:
    app = create_app(Settings())
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def add_article(
    db: Session,
    title: str,
    source: str = "Example News",
    published: datetime = NOW,
    sentiment: str | None = None,
    score: float = 0.0,
) -> Article:
    """An article, analyzed with a chosen sentiment/score when `sentiment` is given."""
    article = Article(
        url=f"https://example.com/{title.replace(' ', '-')}",
        provider="fake",
        provider_article_id=title,
        title=title,
        description=f"About {title}",
        snippet=None,
        image_url=None,
        source_name=source,
        source_url=None,
        published_at=published,
    )
    db.add(article)
    db.flush()
    if sentiment:
        db.add(
            Analysis(
                article_id=article.id,
                tldr=f"Summary of {title}",
                key_points=[],
                sentiment=sentiment,
                score=score,
                rationale="test",
                evidence=[],
                text_source="snippet",
                model="fake",
                prompt_version="test",
            )
        )
    db.flush()
    return article


@pytest.fixture
def library(db: Session) -> dict[str, Article]:
    """Five analyzed articles across sources, dates and sentiments, plus one unanalyzed."""
    articles = {
        "good": add_article(db, "good news", "Alpha", NOW - timedelta(hours=1), "positive", 0.8),
        "okay": add_article(db, "okay news", "Alpha", NOW - timedelta(days=2), "neutral", 0.1),
        "bad": add_article(db, "bad news", "Beta", NOW - timedelta(days=3), "negative", -0.6),
        "worse": add_article(db, "worse news", "Beta", NOW - timedelta(days=10), "negative", -0.9),
        "great": add_article(db, "great news", "Gamma", NOW - timedelta(hours=5), "positive", 0.4),
        "raw": add_article(db, "unanalyzed news", "Gamma", NOW),
    }
    return articles


def titles(res) -> list[str]:  # type: ignore[no-untyped-def]
    return [item["title"] for item in res.json()["items"]]


# --- list ---------------------------------------------------------------------------------


def test_history_lists_analyzed_articles_newest_first_with_analysis(
    client: TestClient, library: dict[str, Article]
) -> None:
    res = client.get("/api/articles", params={"analyzed": "true"})

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 5
    assert titles(res) == ["good news", "great news", "okay news", "bad news", "worse news"]
    assert all(item["analysis"] is not None for item in body["items"])


def test_unanalyzed_filter(client: TestClient, library: dict[str, Article]) -> None:
    res = client.get("/api/articles", params={"analyzed": "false"})
    assert titles(res) == ["unanalyzed news"]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"sentiment": "negative"}, {"bad news", "worse news"}),
        ({"source": "Alpha"}, {"good news", "okay news"}),
        (
            {"published_from": (NOW - timedelta(days=2, hours=1)).isoformat()},
            {"good news", "great news", "okay news"},
        ),
        (
            {"published_to": (NOW - timedelta(days=2, hours=1)).isoformat()},
            {"bad news", "worse news"},
        ),
        ({"sentiment": "positive", "source": "Gamma"}, {"great news"}),
    ],
)
def test_filters(
    client: TestClient, library: dict[str, Article], params: dict[str, str], expected: set[str]
) -> None:
    res = client.get("/api/articles", params={"analyzed": "true", **params})
    assert set(titles(res)) == expected
    assert res.json()["total"] == len(expected)


def test_filter_by_originating_search(
    client: TestClient, db: Session, library: dict[str, Article]
) -> None:
    search = Search(
        provider="fake", query="q", sort="latest", period=None, cache_key="k", result_count=2
    )
    db.add(search)
    db.flush()
    db.add_all(
        [
            SearchResult(search_id=search.id, article_id=library["good"].id, rank=0),
            SearchResult(search_id=search.id, article_id=library["bad"].id, rank=1),
        ]
    )
    db.flush()

    res = client.get("/api/articles", params={"analyzed": "true", "search_id": search.id})

    assert set(titles(res)) == {"good news", "bad news"}


@pytest.mark.parametrize(
    ("sort", "expected_first"),
    [
        ("published_desc", "good news"),
        ("published_asc", "worse news"),
        ("score_desc", "good news"),
        ("score_asc", "worse news"),
    ],
)
def test_sorting(
    client: TestClient, library: dict[str, Article], sort: str, expected_first: str
) -> None:
    res = client.get("/api/articles", params={"analyzed": "true", "sort": sort})
    assert titles(res)[0] == expected_first


def test_pagination(client: TestClient, library: dict[str, Article]) -> None:
    res = client.get("/api/articles", params={"analyzed": "true", "limit": 2, "offset": 2})
    body = res.json()
    assert (body["total"], body["limit"], body["offset"]) == (5, 2, 2)
    assert titles(res) == ["okay news", "bad news"]


@pytest.mark.parametrize(
    "params", [{"sentiment": "happy"}, {"sort": "random"}, {"limit": 0}, {"limit": 101}]
)
def test_invalid_params_are_422(client: TestClient, params: dict[str, str | int]) -> None:
    assert client.get("/api/articles", params=params).status_code == 422


# --- stats --------------------------------------------------------------------------------


def test_stats_summarize_analyzed_articles(client: TestClient, library: dict[str, Article]) -> None:
    body = client.get("/api/stats").json()

    assert body["total"] == 5
    assert body["by_sentiment"] == {"positive": 2, "neutral": 1, "negative": 2}
    assert body["average_score"] == pytest.approx((0.8 + 0.1 - 0.6 - 0.9 + 0.4) / 5)
    assert body["sources"] == ["Alpha", "Beta", "Gamma"]


def test_stats_follow_the_same_filters_as_the_list(
    client: TestClient, library: dict[str, Article]
) -> None:
    body = client.get("/api/stats", params={"source": "Beta"}).json()

    assert body["total"] == 2
    assert body["by_sentiment"] == {"positive": 0, "neutral": 0, "negative": 2}
    assert body["average_score"] == pytest.approx(-0.75)
    assert body["sources"] == ["Alpha", "Beta", "Gamma"]  # dropdown options don't shrink


def test_stats_with_no_analyses(client: TestClient) -> None:
    body = client.get("/api/stats").json()
    assert body["total"] == 0
    assert body["average_score"] is None
