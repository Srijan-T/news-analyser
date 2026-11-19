"""Database models. Import them here so Alembic's autogenerate sees every table."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Search(Base):
    """One real call to the news provider. Repeats within the cache window reuse the row
    instead of creating a new one, so counting today's rows gives today's API usage."""

    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    query: Mapped[str] = mapped_column(String(200))
    sort: Mapped[str] = mapped_column(String(16))
    period: Mapped[str | None] = mapped_column(String(8))
    # provider + normalized query + sort + period: identical searches share a key.
    cache_key: Mapped[str] = mapped_column(String(300), index=True)
    result_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    results: Mapped[list["SearchResult"]] = relationship(
        back_populates="search", order_by="SearchResult.rank", cascade="all, delete-orphan"
    )


class Article(Base):
    """A news article, stored once however many searches return it (unique by URL)."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_article_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SearchResult(Base):
    """Which articles a search returned, in the provider's order."""

    __tablename__ = "search_results"

    search_id: Mapped[int] = mapped_column(
        ForeignKey("searches.id", ondelete="CASCADE"), primary_key=True
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    rank: Mapped[int] = mapped_column(Integer)

    search: Mapped[Search] = relationship(back_populates="results")
    article: Mapped[Article] = relationship()
