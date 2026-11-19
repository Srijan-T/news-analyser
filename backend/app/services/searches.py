"""Searches: run them through the news provider, cache them, and enforce the daily quota.

A row in `searches` exists only for a real provider call, so:
- a repeat of the same search within CACHE_TTL reuses the stored row (no API call), and
- counting today's rows for a provider gives today's API usage.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models import Article, Search, SearchResult
from app.services.news.base import NewsProvider, NewsProviderError, NormalizedArticle, SearchParams

CACHE_TTL = timedelta(minutes=30)


@dataclass(frozen=True)
class QuotaStatus:
    provider: str
    limit: int | None
    used: int

    @property
    def remaining(self) -> int | None:
        return None if self.limit is None else max(self.limit - self.used, 0)


def cache_key(provider: str, params: SearchParams) -> str:
    """Searches that differ only in case or spacing share a key."""
    query = " ".join(params.q.lower().split())
    return f"{provider}|{query}|{params.sort}|{params.period or ''}"


def run_search(
    db: Session,
    provider: NewsProvider,
    params: SearchParams,
    daily_limit: int | None,
    now: datetime | None = None,
) -> tuple[Search, bool]:
    """Return (search, created). Serves a fresh cached search if there is one; otherwise checks
    the quota, calls the provider and stores the results."""
    now = now or datetime.now(UTC)
    key = cache_key(provider.name, params)

    cached = db.scalars(
        select(Search)
        .where(Search.cache_key == key, Search.created_at >= now - CACHE_TTL)
        .order_by(Search.created_at.desc())
        .limit(1)
    ).first()
    if cached is not None:
        return cached, False

    quota = quota_status(db, provider.name, daily_limit, now)
    if quota.remaining == 0:
        raise NewsProviderError.quota_exceeded(
            f"Today's limit of {daily_limit} new searches is used up; it resets at 00:00 UTC. "
            "Recent searches still work."
        )

    articles = provider.search(params)  # raises NewsProviderError; nothing stored on failure

    search = Search(
        provider=provider.name,
        query=params.q,
        sort=params.sort,
        period=params.period,
        cache_key=key,
        result_count=len(articles),
    )
    db.add(search)
    db.flush()  # assigns search.id
    article_ids = _upsert_articles(db, articles)
    db.add_all(
        SearchResult(search_id=search.id, article_id=article_ids[a.url], rank=rank)
        for rank, a in enumerate(articles)
    )
    db.commit()
    db.refresh(search)
    return search, True


def _upsert_articles(db: Session, articles: list[NormalizedArticle]) -> dict[str, int]:
    """Insert new articles and refresh known ones (matched by URL). Returns url -> id."""
    unique = {a.url: a for a in articles}  # a URL twice in one batch would fail ON CONFLICT
    if not unique:
        return {}
    stmt = insert(Article).values(
        [
            {
                "url": a.url,
                "provider": a.provider,
                "provider_article_id": a.provider_article_id,
                "title": a.title,
                "description": a.description,
                "snippet": a.snippet,
                "image_url": a.image_url,
                "source_name": a.source_name,
                "source_url": a.source_url,
                "published_at": a.published_at,
            }
            for a in unique.values()
        ]
    )
    updatable = ("title", "description", "snippet", "image_url", "source_name", "source_url")
    stmt = stmt.on_conflict_do_update(
        index_elements=[Article.url],
        set_={column: stmt.excluded[column] for column in updatable} | {"updated_at": func.now()},
    ).returning(Article.url, Article.id)
    return {url: article_id for url, article_id in db.execute(stmt)}


def get_search(db: Session, search_id: int) -> Search | None:
    return db.scalars(
        select(Search)
        .where(Search.id == search_id)
        .options(selectinload(Search.results).selectinload(SearchResult.article))
    ).first()


def list_searches(db: Session, limit: int, offset: int) -> tuple[list[Search], int]:
    total = db.scalar(select(func.count()).select_from(Search)) or 0
    page = db.scalars(
        select(Search)
        .order_by(Search.created_at.desc(), Search.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(page), total


def quota_status(
    db: Session, provider: str, daily_limit: int | None, now: datetime | None = None
) -> QuotaStatus:
    """Real provider calls since 00:00 UTC today (when GNews resets its quota)."""
    now = now or datetime.now(UTC)
    start_of_day = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    used = db.scalar(
        select(func.count())
        .select_from(Search)
        .where(Search.provider == provider, Search.created_at >= start_of_day)
    )
    return QuotaStatus(provider=provider, limit=daily_limit, used=used or 0)
