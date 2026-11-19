from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    AnalysisOut,
    ArticleOut,
    ArticlePage,
    SentimentCounts,
    SimilarArticles,
    StatsOut,
)
from app.services import analyses, history
from app.services.ai import get_analyzer
from app.services.ai.base import Analyzer, Sentiment
from app.services.history import ArticleFilters, ArticleSort

router = APIRouter(tags=["articles"])

DbSession = Annotated[Session, Depends(get_db)]


def article_filters(
    analyzed: Annotated[bool | None, Query(description="Only (un)analyzed articles")] = None,
    sentiment: Sentiment | None = None,
    source: Annotated[str | None, Query(max_length=200)] = None,
    search_id: Annotated[int | None, Query(description="Only results of this search")] = None,
    published_from: datetime | None = None,
    published_to: datetime | None = None,
) -> ArticleFilters:
    return ArticleFilters(
        analyzed=analyzed,
        sentiment=sentiment,
        source=source,
        search_id=search_id,
        published_from=published_from,
        published_to=published_to,
    )


Filters = Annotated[ArticleFilters, Depends(article_filters)]


@router.get("/articles", response_model=ArticlePage, summary="Stored articles, filterable")
def list_articles(
    db: DbSession,
    filters: Filters,
    sort: ArticleSort = "published_desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ArticlePage:
    page, total = history.list_articles(db, filters, sort, limit, offset)
    return ArticlePage(
        items=[ArticleOut.model_validate(a) for a in page], total=total, limit=limit, offset=offset
    )


@router.get(
    "/stats",
    response_model=StatsOut,
    summary="Sentiment summary of analyzed articles (same filters as /articles)",
)
def stats(db: DbSession, filters: Filters) -> StatsOut:
    result = history.stats(db, filters)
    return StatsOut(
        total=result.total,
        by_sentiment=SentimentCounts(**result.by_sentiment),
        average_score=result.average_score,
        sources=result.sources,
    )


# Declared before /articles/{article_id} so "similar" isn't parsed as an article id.
@router.get(
    "/articles/similar",
    response_model=SimilarArticles,
    summary="Stored articles whose titles fuzzily match a query (no news-API call)",
)
def similar_articles(
    db: DbSession,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> SimilarArticles:
    items = history.similar_articles(db, q.strip(), limit)
    return SimilarArticles(items=[ArticleOut.model_validate(a) for a in items])


@router.get(
    "/articles/{article_id}",
    response_model=ArticleOut,
    summary="An article with its analysis (null if not analyzed yet)",
    responses={404: {"description": "No such article"}},
)
def get_article(article_id: int, db: DbSession) -> ArticleOut:
    return ArticleOut.model_validate(analyses.get_article(db, article_id))


@router.post(
    "/articles/{article_id}/analysis",
    response_model=AnalysisOut,
    status_code=201,
    summary="Summarize the article and score its sentiment with AI",
    responses={
        200: {"description": "Already analyzed; the stored analysis is returned"},
        404: {"description": "No such article"},
        502: {"description": "The AI failed or returned an unusable answer; nothing stored"},
    },
)
def analyze_article(
    article_id: int,
    response: Response,
    db: DbSession,
    analyzer: Annotated[Analyzer, Depends(get_analyzer)],
) -> AnalysisOut:
    analysis, created = analyses.analyze_article(db, analyzer, article_id)
    if not created:
        response.status_code = 200
    return AnalysisOut.model_validate(analysis)
