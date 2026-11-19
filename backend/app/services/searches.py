"""Searches: run them through the news provider, cache them, and enforce the daily quota.

A row in `searches` exists only for real provider calls, so:
- a repeat of the same search within CACHE_TTL reuses the stored row (no API call), and
- summing today's `provider_requests` gives today's API usage.

Forgiving search: when a search finds nothing, retry once with a typo-corrected query and
then once with "match any word" (at most 3 provider calls), storing whichever found results.
"""

import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models import Article, Search, SearchResult
from app.services.news.base import NewsProvider, NewsProviderError, NormalizedArticle, SearchParams
from app.services.query_fix import OPERATORS, QueryCorrector

CACHE_TTL = timedelta(minutes=30)


@dataclass(frozen=True)
class QuotaStatus:
    provider: str
    limit: int | None
    used: int

    @property
    def remaining(self) -> int | None:
        return None if self.limit is None else max(self.limit - self.used, 0)


def cache_key(provider: str, params: SearchParams, exact: bool = False) -> str:
    """Searches that differ only in case or spacing share a key. Keyed on what was *typed*,
    so repeating a typo reuses the stored corrected result. Exact searches (no fallbacks)
    are cached separately."""
    query = " ".join(params.q.lower().split())
    return f"{provider}|{query}|{params.sort}|{params.period or ''}" + ("|exact" if exact else "")


def broaden(query: str) -> str | None:
    """'environmental improvements' -> 'environmental OR improvements' (GNews syntax), or None
    when there's nothing to broaden (one word, or the query already uses operators)."""
    tokens = query.split()
    if len(tokens) < 2 or any(t in OPERATORS for t in tokens):
        return None
    # GNews: put quotes around any word with a character other than a letter or a digit.
    quoted = [t if re.fullmatch(r"[A-Za-z0-9]+", t) or '"' in t else f'"{t}"' for t in tokens]
    return " OR ".join(quoted)


def run_search(
    db: Session,
    provider: NewsProvider,
    params: SearchParams,
    daily_limit: int | None,
    corrector: QueryCorrector | None = None,
    *,
    exact: bool = False,
    min_interval: float = 0.0,
    now: datetime | None = None,
) -> tuple[Search, bool]:
    """Return (search, created). Serves a fresh cached search if there is one; otherwise checks
    the quota, calls the provider (with fallbacks unless `exact`) and stores the results."""
    now = now or datetime.now(UTC)
    key = cache_key(provider.name, params, exact)

    cached = _fresh_search(db, key, now)
    if cached is not None:
        return cached, False

    # Only one new search per provider at a time: without this, concurrent requests near the
    # limit could all read the same count and all call the provider. The transaction-scoped
    # advisory lock is released at commit/rollback. GNews's free plan allows 1 request/second
    # anyway, so serializing costs nothing in practice.
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"news-search:{provider.name}"))))

    # While we waited, another request may have just run this same search.
    cached = _fresh_search(db, key, now)
    if cached is not None:
        return cached, False

    quota = quota_status(db, provider.name, daily_limit, now)
    if quota.remaining == 0:
        raise NewsProviderError.quota_exceeded(
            f"Today's limit of {daily_limit} new searches is used up; it resets at 00:00 UTC. "
            "Recent searches still work."
        )

    calls = _ProviderCalls(provider, params, budget=quota.remaining, min_interval=min_interval)
    # The first call's errors reach the client (400 bad query, 429, 502...); nothing stored.
    articles = calls.run(params.q)
    ran_query, match_mode = params.q, "all"

    if not articles and not exact:
        ran_query, match_mode, articles = _fallbacks(calls, params.q, corrector)

    search = Search(
        provider=provider.name,
        query=ran_query,
        original_query=params.q if ran_query != params.q else None,
        sort=params.sort,
        period=params.period,
        cache_key=key,
        match_mode=match_mode,
        result_count=len(articles),
        provider_requests=calls.made,
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


class _ProviderCalls:
    """Makes provider calls for one search: counts them (they all spend quota), keeps within
    the remaining daily budget, and spaces them out (GNews free allows 1 request/second)."""

    def __init__(
        self, provider: NewsProvider, params: SearchParams, budget: int | None, min_interval: float
    ) -> None:
        self._provider = provider
        self._params = params
        self._budget = budget
        self._min_interval = min_interval
        self._last_call: float | None = None
        self.made = 0

    @property
    def can_call(self) -> bool:
        return self._budget is None or self.made < self._budget

    def run(self, query: str) -> list[NormalizedArticle]:
        if self._last_call is not None and self._min_interval:
            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
        self.made += 1  # a failed call still counts against the provider's quota
        try:
            results = self._provider.search(self._params.model_copy(update={"q": query}))
        finally:
            self._last_call = time.monotonic()
        # Providers occasionally repeat an article, which would break the
        # (search_id, article_id) key, so keep the first of each. The same story can also
        # come back under a second URL (e.g. after a headline edit): drop those too.
        return drop_near_duplicates(_dedupe_by_url(results))


def _fallbacks(
    calls: _ProviderCalls, query: str, corrector: QueryCorrector | None
) -> tuple[str, str, list[NormalizedArticle]]:
    """After an empty first search: try the corrected query, then "match any word".
    Returns (query that ran, match mode, articles); the original query if nothing helped.
    A failing or over-budget fallback just stops here; the first call already succeeded."""
    corrected = corrector.suggest(query) if corrector else None
    if corrected and corrected.lower() == query.lower():
        corrected = None
    candidates = [(corrected, "all"), (broaden(corrected or query), "any")]
    for candidate, mode in candidates:
        if not candidate or not calls.can_call:
            continue
        try:
            articles = calls.run(candidate)
        except NewsProviderError:
            break
        if articles:
            return candidate, mode, articles
    return query, "all", []


def _dedupe_by_url(articles: list[NormalizedArticle]) -> list[NormalizedArticle]:
    """Keep the first occurrence of each URL, in the provider's order."""
    unique: dict[str, NormalizedArticle] = {}
    for article in articles:
        unique.setdefault(article.url, article)
    return list(unique.values())


# Titles at least this similar (difflib ratio, after normalizing) may be the same story, but
# only with corroborating evidence: one outlet's "Tesla stock jumps/drops 5% on delivery
# numbers" scores 0.92, so a shared source isn't enough.
SIMILAR_TITLE = 0.9


def _normalized_title(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", title.lower()))


def _same_story(a: NormalizedArticle, b: NormalizedArticle) -> bool:
    """Identical headlines (wire stories republished verbatim), or near-identical ones that
    also share the description or image (a re-published or edited article)."""
    ta, tb = _normalized_title(a.title), _normalized_title(b.title)
    if ta == tb:
        return True
    if SequenceMatcher(None, ta, tb).ratio() < SIMILAR_TITLE:
        return False
    return (a.description is not None and a.description == b.description) or (
        a.image_url is not None and a.image_url == b.image_url
    )


def drop_near_duplicates(articles: list[NormalizedArticle]) -> list[NormalizedArticle]:
    """Keep the first copy of each story, in the provider's order (at most 10 articles, so
    comparing every pair is cheap)."""
    kept: list[NormalizedArticle] = []
    for article in articles:
        if not any(_same_story(article, k) for k in kept):
            kept.append(article)
    return kept


def _fresh_search(db: Session, key: str, now: datetime) -> Search | None:
    return db.scalars(
        select(Search)
        .where(Search.cache_key == key, Search.created_at >= now - CACHE_TTL)
        .order_by(Search.created_at.desc())
        .limit(1)
    ).first()


def _upsert_articles(db: Session, articles: list[NormalizedArticle]) -> dict[str, int]:
    """Insert new articles and refresh known ones (matched by URL). Returns url -> id."""
    unique = {a.url: a for a in articles}  # already unique; kept as a guard for ON CONFLICT
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
        .options(
            selectinload(Search.results)
            .selectinload(SearchResult.article)
            .selectinload(Article.analysis)  # one query for all analyses, not one per article
        )
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
    # Sum provider calls rather than counting rows: one search can make up to 3 (exact,
    # corrected, broadened), and every one spends quota.
    used = db.scalar(
        select(func.coalesce(func.sum(Search.provider_requests), 0)).where(
            Search.provider == provider, Search.created_at >= start_of_day
        )
    )
    return QuotaStatus(provider=provider, limit=daily_limit, used=used or 0)
