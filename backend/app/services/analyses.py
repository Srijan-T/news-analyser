"""Analyses: run the AI over an article once and store the result."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError
from app.models import Analysis, Article
from app.services.ai.base import Analyzer, ArticleText
from app.services.ai.prompts import PROMPT_VERSION


def get_article(db: Session, article_id: int) -> Article:
    article = db.scalars(
        select(Article).where(Article.id == article_id).options(selectinload(Article.analysis))
    ).first()
    if article is None:
        raise AppError(404, "article_not_found", f"Article {article_id} doesn't exist")
    return article


def analyze_article(db: Session, analyzer: Analyzer, article_id: int) -> tuple[Analysis, bool]:
    """Return (analysis, created). An article is analyzed at most once; asking again returns
    the stored analysis without calling the AI."""
    article = get_article(db, article_id)
    if article.analysis is not None:
        return article.analysis, False

    # Raises AnalysisError (502) on failure, before anything is written.
    result = analyzer.analyze(
        ArticleText(
            title=article.title,
            description=article.description,
            snippet=article.snippet,
            source_name=article.source_name,
        )
    )
    draft = result.draft
    analysis = Analysis(
        article_id=article.id,
        tldr=draft.tldr,
        key_points=draft.key_points,
        sentiment=draft.sentiment,
        score=draft.score,
        rationale=draft.rationale,
        evidence=draft.evidence,
        # The free GNews plan only provides the article's opening (~250 characters).
        text_source="snippet",
        model=result.model,
        prompt_version=PROMPT_VERSION,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    db.add(analysis)
    try:
        db.commit()
    except IntegrityError:
        # Another request analyzed this article at the same moment; keep theirs.
        db.rollback()
        return get_article(db, article_id).analysis or analysis, False
    return analysis, True
