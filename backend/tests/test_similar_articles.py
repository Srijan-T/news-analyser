"""Fuzzy matches among already-stored articles: shown when a search finds nothing, at no quota."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.main import create_app
from app.models import Article
from app.services.news import get_news_provider


class ExplodingProvider:
    name = "gnews"

    def search(self, params: object) -> list[object]:
        raise AssertionError("similar articles must never call the news provider")


@pytest.fixture
def client(db: Session) -> TestClient:
    for i, title in enumerate(
        [
            "Environmental improvements planned for city parks",
            "Council approves environmental plan",
            "Banana prices hit a record high",
        ]
    ):
        db.add(
            Article(
                url=f"https://example.com/{i}",
                provider="gnews",
                provider_article_id=str(i),
                title=title,
                description=None,
                snippet=None,
                image_url=None,
                source_name="Example",
                source_url=None,
                published_at=datetime(2026, 11, 19, tzinfo=UTC),
            )
        )
    db.flush()
    app = create_app(Settings())
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_news_provider] = ExplodingProvider
    return TestClient(app)


def titles(res) -> list[str]:  # type: ignore[no-untyped-def]
    return [a["title"] for a in res.json()["items"]]


def test_misspelled_query_finds_stored_articles(client: TestClient) -> None:
    res = client.get("/api/articles/similar", params={"q": "enviromental improvemenets"})

    assert res.status_code == 200
    assert titles(res)[0] == "Environmental improvements planned for city parks"
    assert "Banana prices hit a record high" not in titles(res)


def test_unrelated_query_finds_nothing(client: TestClient) -> None:
    assert titles(client.get("/api/articles/similar", params={"q": "quantum computing"})) == []


def test_limit_and_validation(client: TestClient) -> None:
    res = client.get("/api/articles/similar", params={"q": "environmental", "limit": 1})
    assert len(titles(res)) == 1
    assert client.get("/api/articles/similar").status_code == 422
    assert client.get("/api/articles/similar", params={"q": "x", "limit": 50}).status_code == 422


def test_article_detail_route_still_works(client: TestClient) -> None:
    # "/articles/similar" must not be swallowed by "/articles/{article_id}" (or vice versa).
    assert client.get("/api/articles/999999").json()["error"]["code"] == "article_not_found"


def test_similarity_filter_can_use_the_trigram_index(db: Session) -> None:
    """A function compared to a number can't use the GIN index; pg_trgm's operator can. With
    sequential scans disabled, the planner must find an index path for our query."""
    from sqlalchemy import text
    from sqlalchemy.dialects import postgresql

    from app.services.history import similar_articles_statement

    sql = similar_articles_statement("enviromental improvemenets", 5).compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    db.execute(text("SET LOCAL enable_seqscan = off"))
    # Rendering for the psycopg driver escapes "%" as "%%"; undo it for this raw EXPLAIN.
    raw = str(sql).replace("%%", "%")
    plan = "\n".join(row[0] for row in db.execute(text(f"EXPLAIN {raw}")))

    assert "ix_articles_title_trgm" in plan
