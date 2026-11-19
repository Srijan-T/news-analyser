"""API request and response models (what clients see), separate from database models."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.ai.base import Sentiment
from app.services.news.base import Period, SortOrder

Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class CreateSearch(BaseModel):
    q: Query = Field(description="Search terms (GNews query syntax)")
    sort: SortOrder = "latest"
    period: Period | None = None


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
