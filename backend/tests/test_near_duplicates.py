"""One story can reach a search twice under different URLs, e.g. after the publisher edits a
headline typo ("unphased" -> "unfazed") and the slug changes. Show it once."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.main import create_app
from app.services.news import get_news_provider
from app.services.news.base import NormalizedArticle, SearchParams
from app.services.searches import drop_near_duplicates

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)


def article(
    n: int,
    title: str,
    source: str = "TechCrunch",
    description: str | None = None,
    image_url: str | None = None,
) -> NormalizedArticle:
    return NormalizedArticle(
        provider="gnews",
        provider_article_id=f"a{n}",
        title=title,
        description=description,
        snippet=None,
        url=f"https://example.com/{n}",
        image_url=image_url,
        source_name=source,
        source_url=None,
        published_at=NOW,
    )


QUOTE = (
    "\"It doesn't feel like it's in like the top 10 weirdest things about my life,\" Altman said."
)
FAZED = "Sam Altman says his life is so weird that he's unfazed by Andrew Garfield portraying him"
PHASED = "Sam Altman says his life is so weird that he's unphased by Andrew Garfield portraying him"


def titles(articles: list[NormalizedArticle]) -> list[str]:
    return [a.title for a in articles]


def test_edited_headline_with_the_same_description_is_dropped() -> None:
    first = article(1, FAZED, description=QUOTE)
    edited = article(2, PHASED, description=QUOTE)
    other = article(3, "Jensen Huang Is Top of Mind for Tech Leaders at DealBook Summit")

    assert titles(drop_near_duplicates([first, edited, other])) == [FAZED, other.title]


def test_near_identical_headline_with_the_same_image_is_dropped() -> None:
    first = article(1, FAZED, image_url="https://img/1.jpg")
    edited = article(2, PHASED, description="Reworded summary.", image_url="https://img/1.jpg")

    assert titles(drop_near_duplicates([first, edited])) == [FAZED]


def test_identical_headlines_from_different_outlets_are_dropped() -> None:
    """A wire story (AP, Reuters) republished word for word by several outlets."""
    wire = "Fed holds interest rates steady, signals two cuts next year"
    result = drop_near_duplicates(
        [article(1, wire, source="AP"), article(2, wire.upper() + ".", source="Yahoo News")]
    )

    assert [a.source_name for a in result] == ["AP"]


@pytest.mark.parametrize(
    ("a", "b"),
    [
        # Similar wording, opposite stories, different outlets: both stay.
        (
            article(1, "Nvidia earnings beat expectations", source="Reuters"),
            article(2, "Nvidia earnings miss expectations", source="CNBC"),
        ),
        # Same source, titles 0.92 similar, opposite news: a shared source isn't enough.
        (
            article(1, "Tesla stock jumps 5% on delivery numbers", description="Up."),
            article(2, "Tesla stock drops 5% on delivery numbers", description="Down."),
        ),
    ],
    ids=["opposite-stories", "same-source-different-story"],
)
def test_distinct_stories_are_kept(a: NormalizedArticle, b: NormalizedArticle) -> None:
    assert len(drop_near_duplicates([a, b])) == 2


SAFETY = "Sam Altman On 'Artificial' Movie And Need For Hard Look At AI Safety"


class EditedHeadlineProvider:
    name = "gnews"

    def search(self, params: SearchParams) -> list[NormalizedArticle]:
        return [
            article(1, FAZED, description=QUOTE),
            article(2, PHASED, description=QUOTE),
            article(3, SAFETY),
        ]


@pytest.fixture
def client(db: Session) -> TestClient:
    app = create_app(Settings())
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_news_provider] = EditedHeadlineProvider
    return TestClient(app)


def test_search_stores_and_returns_one_copy(client: TestClient) -> None:
    body = client.post("/api/searches", json={"q": "altman"}).json()

    assert [a["title"] for a in body["items"]] == [FAZED, SAFETY]
    assert body["result_count"] == 2
