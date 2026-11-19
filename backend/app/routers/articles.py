from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import AnalysisOut, ArticleOut
from app.services import analyses
from app.services.ai import get_analyzer
from app.services.ai.base import Analyzer

router = APIRouter(prefix="/articles", tags=["articles"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/{article_id}",
    response_model=ArticleOut,
    summary="An article with its analysis (null if not analyzed yet)",
    responses={404: {"description": "No such article"}},
)
def get_article(article_id: int, db: DbSession) -> ArticleOut:
    return ArticleOut.model_validate(analyses.get_article(db, article_id))


@router.post(
    "/{article_id}/analysis",
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
