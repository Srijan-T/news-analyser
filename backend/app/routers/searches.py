from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.errors import AppError
from app.models import Search
from app.schemas import ArticleOut, CreateSearch, QuotaOut, SearchOut, SearchPage, SearchSummary
from app.services import searches
from app.services.news import get_news_provider
from app.services.news.base import NewsProvider, SearchParams
from app.services.query_fix import QueryCorrector, get_query_corrector

router = APIRouter(tags=["searches"])

DbSession = Annotated[Session, Depends(get_db)]
Provider = Annotated[NewsProvider, Depends(get_news_provider)]


def _daily_limit(request: Request, provider: NewsProvider) -> int | None:
    """The offline fake provider costs nothing, so it has no quota."""
    settings: Settings = request.app.state.settings
    return None if provider.name == "fake" else settings.news_daily_request_limit


def _to_out(search: Search) -> SearchOut:
    return SearchOut(
        **SearchSummary.model_validate(search).model_dump(),
        items=[ArticleOut.model_validate(r.article) for r in search.results],
    )


@router.post(
    "/searches",
    response_model=SearchOut,
    status_code=201,
    summary="Run a news search (or reuse an identical one from the last 30 minutes)",
    responses={
        200: {"description": "Identical recent search reused from cache; no API call made"},
        400: {"description": "Invalid query syntax"},
        429: {"description": "Daily news quota reached, or rate limited"},
        502: {"description": "News provider failed"},
    },
)
def create_search(
    body: CreateSearch,
    request: Request,
    response: Response,
    db: DbSession,
    provider: Provider,
    corrector: Annotated[QueryCorrector, Depends(get_query_corrector)],
) -> SearchOut:
    settings: Settings = request.app.state.settings
    params = SearchParams(q=body.q, sort=body.sort, period=body.period)
    search, created = searches.run_search(
        db,
        provider,
        params,
        _daily_limit(request, provider),
        corrector,
        exact=body.exact,
        min_interval=settings.news_min_request_interval,
    )
    if not created:
        response.status_code = 200
    return _to_out(searches.get_search(db, search.id) or search)


@router.get("/searches", response_model=SearchPage, summary="Search history, newest first")
def list_searches(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchPage:
    page, total = searches.list_searches(db, limit, offset)
    return SearchPage(
        items=[SearchSummary.model_validate(s) for s in page],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/searches/{search_id}",
    response_model=SearchOut,
    summary="A stored search with its articles",
    responses={404: {"description": "No such search"}},
)
def get_search(search_id: int, db: DbSession) -> SearchOut:
    search = searches.get_search(db, search_id)
    if search is None:
        raise AppError(404, "search_not_found", f"Search {search_id} doesn't exist")
    return _to_out(search)


@router.get("/quota", response_model=QuotaOut, summary="News API requests used and left today")
def quota(request: Request, db: DbSession, provider: Provider) -> QuotaOut:
    status = searches.quota_status(db, provider.name, _daily_limit(request, provider))
    return QuotaOut(
        provider=status.provider, limit=status.limit, used=status.used, remaining=status.remaining
    )
