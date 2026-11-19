from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="App and database health",
    responses={503: {"description": "Database unreachable"}},
)
def health(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    # Railway's health check hits this, so a deploy that can't reach Postgres never
    # replaces a working one.
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise AppError(503, "database_unavailable", "The database is unreachable") from exc
    return HealthResponse(status="ok", database="ok")
