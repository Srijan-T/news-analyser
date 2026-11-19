from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.errors import AppError
from app.services.news import get_news_provider
from app.services.news.base import (
    NewsProvider,
    NormalizedArticle,
    Period,
    SearchParams,
    SortOrder,
)

router = APIRouter(prefix="/news", tags=["news"])


class NewsSearchResponse(BaseModel):
    provider: str
    query: str
    items: list[NormalizedArticle]


ERROR_RESPONSES: dict[int | str, dict[str, str]] = {
    400: {"description": "Invalid query syntax"},
    429: {"description": "News API quota or rate limit reached"},
    502: {"description": "News provider failed or rejected our credentials"},
}


@router.get(
    "/search",
    response_model=NewsSearchResponse,
    summary="Search recent news articles",
    responses=ERROR_RESPONSES,
)
def search_news(
    provider: Annotated[NewsProvider, Depends(get_news_provider)],
    q: Annotated[str, Query(min_length=1, max_length=200, description="Search terms")],
    sort: Annotated[SortOrder, Query()] = "latest",
    period: Annotated[Period | None, Query(description="Only articles from this window")] = None,
) -> NewsSearchResponse:
    query = q.strip()
    if not query:
        raise AppError(422, "validation_error", "Search terms can't be blank")
    items = provider.search(SearchParams(q=query, sort=sort, period=period))
    return NewsSearchResponse(provider=provider.name, query=query, items=items)
