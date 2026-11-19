from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AnalysisBatch
from app.schemas import (
    AnalysisBatchOut,
    AnalysisOut,
    BatchCounts,
    BatchItemOut,
    CreateAnalysisBatch,
)
from app.services import batches
from app.services.batches import BatchRunner, get_batch_runner

router = APIRouter(tags=["analysis batches"])

DbSession = Annotated[Session, Depends(get_db)]


def to_out(batch: AnalysisBatch) -> AnalysisBatchOut:
    now = datetime.now(UTC)
    items: list[BatchItemOut] = []
    for item in batch.items:
        status, error_code = batches.item_state(item, now)
        analysis = item.article.analysis
        items.append(
            BatchItemOut(
                article_id=item.article_id,
                position=item.position,
                status=status,  # pyright: ignore[reportArgumentType]  (DB CHECK constraint)
                error_code=error_code,
                analysis=AnalysisOut.model_validate(analysis) if analysis else None,
            )
        )
    counts = {s: sum(i.status == s for i in items) for s in BatchCounts.model_fields}
    return AnalysisBatchOut(
        id=batch.id,
        status="running" if counts["pending"] or counts["running"] else "done",
        counts=BatchCounts(**counts),
        items=items,
        created_at=batch.created_at,
    )


@router.post(
    "/analysis-batches",
    response_model=AnalysisBatchOut,
    status_code=202,
    summary="Analyze up to 10 articles in the background; poll the Location URL for progress",
    responses={
        404: {"description": "Some article ids don't exist (listed in details); nothing stored"},
        422: {"description": "Empty, more than 10, or repeated article ids"},
    },
)
def create_batch(
    body: CreateAnalysisBatch,
    response: Response,
    background: BackgroundTasks,
    db: DbSession,
    runner: Annotated[BatchRunner, Depends(get_batch_runner)],
) -> AnalysisBatchOut:
    batch = batches.create_batch(db, body.article_ids)
    background.add_task(runner.run, batch.id)  # starts after the 202 has been sent
    response.headers["Location"] = f"/api/analysis-batches/{batch.id}"
    return to_out(batches.get_batch(db, batch.id))


@router.get(
    "/analysis-batches/{batch_id}",
    response_model=AnalysisBatchOut,
    summary="A batch's progress, with each finished analysis",
    responses={404: {"description": "No such batch"}},
)
def get_batch(batch_id: int, db: DbSession) -> AnalysisBatchOut:
    return to_out(batches.get_batch(db, batch_id))
