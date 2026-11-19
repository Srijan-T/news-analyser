"""API request and response models (what clients see), separate from database models."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.services.ai.base import Sentiment
from app.services.news.base import Period, SortOrder

Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class CreateSearch(BaseModel):
    q: Query = Field(description="Search terms (GNews query syntax)")
    sort: SortOrder = "latest"
    period: Period | None = None
    exact: bool = Field(
        default=False,
        description="Search exactly as typed: no typo correction or 'match any word' fallback",
    )


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    article_id: int
    tldr: str
    key_points: list[str]
    sentiment: Sentiment
    score: float = Field(description="-1 (very negative) to 1 (very positive)")
    rationale: str
    evidence: list[str] = Field(description="Short quotes copied from the article text")
    text_source: str = Field(description='"snippet" when only the article opening was available')
    model: str
    prompt_version: str
    created_at: datetime


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    snippet: str | None
    url: str
    image_url: str | None
    source_name: str
    source_url: str | None
    published_at: datetime
    analysis: AnalysisOut | None = None


class SearchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    query: str
    sort: SortOrder
    period: Period | None
    result_count: int
    original_query: str | None = Field(
        description="What was typed, when the query that ran differs (corrected or broadened)"
    )
    match_mode: Literal["all", "any"] = Field(
        description='"any": results match any of the words (broadened after finding nothing)'
    )
    created_at: datetime


class SearchOut(SearchSummary):
    items: list[ArticleOut]


class SearchPage(BaseModel):
    items: list[SearchSummary]
    total: int
    limit: int
    offset: int


class QuotaOut(BaseModel):
    provider: str
    limit: int | None = Field(description="Daily limit; null when the provider has none")
    used: int
    remaining: int | None


class ArticlePage(BaseModel):
    items: list[ArticleOut]
    total: int
    limit: int
    offset: int


class SentimentCounts(BaseModel):
    positive: int
    neutral: int
    negative: int


class StatsOut(BaseModel):
    total: int = Field(description="Analyzed articles matching the filters")
    by_sentiment: SentimentCounts
    average_score: float | None = Field(description="Mean score; null when nothing matches")
    sources: list[str] = Field(description="Every source with an analysis (for filter menus)")


class SimilarArticles(BaseModel):
    items: list[ArticleOut]


MAX_BATCH_SIZE = 10  # bounds one request's AI spend and keeps the job short


class CreateAnalysisBatch(BaseModel):
    article_ids: list[int] = Field(
        min_length=1, max_length=MAX_BATCH_SIZE, description="Articles to analyze, in order"
    )

    @field_validator("article_ids")
    @classmethod
    def unique(cls, ids: list[int]) -> list[int]:
        if len(set(ids)) != len(ids):
            raise ValueError("article ids must be unique")
        return ids


BatchItemStatus = Literal["pending", "running", "done", "skipped", "failed"]


class BatchItemOut(BaseModel):
    article_id: int
    position: int
    status: BatchItemStatus = Field(description='"skipped": the article was already analyzed')
    error_code: str | None = Field(description='Why it failed, e.g. "ai_unavailable"')
    analysis: AnalysisOut | None


class BatchCounts(BaseModel):
    pending: int
    running: int
    done: int
    skipped: int
    failed: int


class AnalysisBatchOut(BaseModel):
    id: int
    status: Literal["running", "done"] = Field(description='"done" once no item is unfinished')
    counts: BatchCounts
    items: list[BatchItemOut]
    created_at: datetime
