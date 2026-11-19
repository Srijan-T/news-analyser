"""Batch analysis: analyze several articles in one request, in a background job.

POST creates the batch (one item per article) and returns 202 straight away; BatchRunner then
works through the pending items with a few worker threads while the client polls GET. Each
item goes through analyses.analyze_article, so the per-article row lock still guarantees one
AI call per article, even if the same article is also analyzed on its own at the same time.

The job runs in-process (FastAPI BackgroundTasks): simple, no extra infrastructure. If the
server restarts mid-batch the job is lost, so items stuck for STALE_AFTER are reported as
failed ("interrupted") rather than leaving the batch running forever.
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError
from app.models import AnalysisBatch, AnalysisBatchItem, Article
from app.services import analyses
from app.services.ai import get_analyzer
from app.services.ai.base import Analyzer

logger = logging.getLogger(__name__)

WORKERS = 3  # parallel AI calls per batch: quick, but gentle on the OpenAI rate limit
STALE_AFTER = timedelta(minutes=10)
UNFINISHED = frozenset({"pending", "running"})


def create_batch(db: Session, article_ids: list[int]) -> AnalysisBatch:
    """Store a batch for these articles (all must exist). Already analyzed ones are marked
    skipped up front, so the job only spends AI calls on new work."""
    articles = db.scalars(
        select(Article).where(Article.id.in_(article_ids)).options(selectinload(Article.analysis))
    ).all()
    found = {a.id: a for a in articles}
    missing = [i for i in article_ids if i not in found]
    if missing:
        raise AppError(
            404, "article_not_found", "Some articles don't exist", {"missing_ids": missing}
        )

    batch = AnalysisBatch(
        items=[
            AnalysisBatchItem(
                article_id=article_id,
                position=position,
                status="skipped" if found[article_id].analysis else "pending",
            )
            for position, article_id in enumerate(article_ids)
        ]
    )
    db.add(batch)
    db.commit()
    return batch


def get_batch(db: Session, batch_id: int) -> AnalysisBatch:
    stmt = (
        select(AnalysisBatch)
        .where(AnalysisBatch.id == batch_id)
        .options(
            selectinload(AnalysisBatch.items)
            .selectinload(AnalysisBatchItem.article)
            .selectinload(Article.analysis)
        )
        # Re-read rows the session already holds: worker threads update them meanwhile.
        .execution_options(populate_existing=True)
    )
    batch = db.scalars(stmt).first()
    if batch is None:
        raise AppError(404, "batch_not_found", f"Analysis batch {batch_id} doesn't exist")
    return batch


def item_state(item: AnalysisBatchItem, now: datetime) -> tuple[str, str | None]:
    """(status, error_code) as reported to clients: unfinished items that haven't moved for
    STALE_AFTER belong to a job that died with the server, so they count as failed."""
    if item.status in UNFINISHED and now - item.updated_at > STALE_AFTER:
        return "failed", "interrupted"
    return item.status, item.error_code


OpenSession = Callable[[], AbstractContextManager[Session]]


class BatchRunner:
    """Analyzes a batch's pending items. Each worker thread opens its own session (sessions
    aren't thread-safe); with workers=1 it runs inline, which tests use with their session."""

    def __init__(self, open_session: OpenSession, analyzer: Analyzer, workers: int = WORKERS):
        self._open_session = open_session
        self._analyzer = analyzer
        self._workers = workers

    def run(self, batch_id: int) -> None:
        with self._open_session() as db:
            pending = db.scalars(
                select(AnalysisBatchItem.article_id)
                .where(
                    AnalysisBatchItem.batch_id == batch_id, AnalysisBatchItem.status == "pending"
                )
                .order_by(AnalysisBatchItem.position)
            ).all()
        if self._workers == 1 or len(pending) <= 1:
            for article_id in pending:
                self._process(batch_id, article_id)
            return
        with ThreadPoolExecutor(max_workers=min(self._workers, len(pending))) as pool:
            # list(): wait for every item and re-raise anything unexpected (logged by Starlette).
            list(pool.map(lambda article_id: self._process(batch_id, article_id), pending))

    def _process(self, batch_id: int, article_id: int) -> None:
        with self._open_session() as db:
            item = db.get_one(AnalysisBatchItem, (batch_id, article_id))
            item.status = "running"
            db.commit()  # visible to pollers while the AI works
            try:
                _, created = analyses.analyze_article(db, self._analyzer, article_id)
            except AppError as exc:  # e.g. the AI failed: record it, carry on with the rest
                db.rollback()
                item.status, item.error_code = "failed", exc.code
            except Exception:
                logger.exception("Batch %s: analysing article %s failed", batch_id, article_id)
                db.rollback()
                item.status, item.error_code = "failed", "internal_error"
            else:
                # Not created: someone analyzed it on its own while the batch was queued.
                item.status = "done" if created else "skipped"
            db.commit()


def get_batch_runner(
    request: Request, analyzer: Annotated[Analyzer, Depends(get_analyzer)]
) -> BatchRunner:
    """FastAPI dependency: the real runner, with a fresh session per worker."""
    return BatchRunner(open_session=request.app.state.session_factory, analyzer=analyzer)
