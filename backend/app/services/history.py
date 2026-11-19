"""Browse stored articles and summarize their analyses.

The list and the stats both go through `_conditions`, so the numbers in the stats strip
always describe exactly the articles the list shows.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Analysis, Article, SearchResult
from app.services.ai.base import Sentiment

ArticleSort = Literal["published_desc", "published_asc", "analyzed_desc", "score_desc", "score_asc"]


@dataclass(frozen=True)
class ArticleFilters:
    analyzed: bool | None = None
    sentiment: Sentiment | None = None
    source: str | None = None
    search_id: int | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None


@dataclass(frozen=True)
class Stats:
    total: int
    by_sentiment: dict[str, int]
    average_score: float | None
    sources: list[str]


def _conditions(filters: ArticleFilters) -> list[ColumnElement[bool]]:
    """WHERE clauses for a query over Article LEFT JOIN Analysis."""
    conditions: list[ColumnElement[bool]] = []
    if filters.analyzed is True:
        conditions.append(Analysis.id.is_not(None))
    elif filters.analyzed is False:
        conditions.append(Analysis.id.is_(None))
    if filters.sentiment:
        conditions.append(Analysis.sentiment == filters.sentiment)
    if filters.source:
        conditions.append(Article.source_name == filters.source)
    if filters.search_id is not None:
        conditions.append(
            Article.id.in_(
                select(SearchResult.article_id).where(SearchResult.search_id == filters.search_id)
            )
        )
    if filters.published_from:
        conditions.append(Article.published_at >= filters.published_from)
    if filters.published_to:
        conditions.append(Article.published_at <= filters.published_to)
    return conditions


def _joined[T: Select](stmt: T) -> T:
    return stmt.outerjoin(Analysis, Analysis.article_id == Article.id)


_ORDER = {
    "published_desc": (Article.published_at.desc(), Article.id.desc()),
    "published_asc": (Article.published_at.asc(), Article.id.asc()),
    "analyzed_desc": (Analysis.created_at.desc().nulls_last(), Article.id.desc()),
    "score_desc": (Analysis.score.desc().nulls_last(), Article.id.desc()),
    "score_asc": (Analysis.score.asc().nulls_last(), Article.id.desc()),
}


def list_articles(
    db: Session, filters: ArticleFilters, sort: ArticleSort, limit: int, offset: int
) -> tuple[list[Article], int]:
    conditions = _conditions(filters)
    total = db.scalar(_joined(select(func.count()).select_from(Article)).where(*conditions)) or 0
    page = db.scalars(
        _joined(select(Article))
        .where(*conditions)
        .order_by(*_ORDER[sort])
        .limit(limit)
        .offset(offset)
        .options(selectinload(Article.analysis))
    ).all()
    return list(page), total


def stats(db: Session, filters: ArticleFilters) -> Stats:
    """Sentiment summary over analyzed articles matching the filters."""
    conditions = [*_conditions(filters), Analysis.id.is_not(None)]
    rows = db.execute(
        _joined(select(Analysis.sentiment, func.count(), func.avg(Analysis.score)))
        .select_from(Article)
        .where(*conditions)
        .group_by(Analysis.sentiment)
    ).all()
    by_sentiment = {"positive": 0, "neutral": 0, "negative": 0}
    total = 0
    score_sum = 0.0
    for sentiment, count, average in rows:
        by_sentiment[sentiment] = count
        total += count
        score_sum += float(average) * count
    # Every source with at least one analysis, regardless of filters, for the filter dropdown.
    sources = db.scalars(
        select(Article.source_name).join(Analysis).distinct().order_by(Article.source_name)
    ).all()
    return Stats(
        total=total,
        by_sentiment=by_sentiment,
        average_score=score_sum / total if total else None,
        sources=list(sources),
    )


SIMILARITY_THRESHOLD = 0.3  # pg_trgm word_similarity: 0 unrelated .. 1 identical


def similar_articles(db: Session, query: str, limit: int) -> list[Article]:
    """Stored articles whose titles fuzzily match `query` (typos included), best first.
    Pure database: never calls the news provider, so it costs no quota."""
    score = func.word_similarity(query, Article.title)
    return list(
        db.scalars(
            select(Article)
            .where(score >= SIMILARITY_THRESHOLD)
            .order_by(score.desc(), Article.published_at.desc())
            .limit(limit)
            .options(selectinload(Article.analysis))
        )
    )
