"""API request and response models (what clients see), separate from database models."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.news.base import Period, SortOrder

Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class CreateSearch(BaseModel):
    q: Query = Field(description="Search terms (GNews query syntax)")
    sort: SortOrder = "latest"
    period: Period | None = None


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
