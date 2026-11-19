"""Concurrency needs real, separately committed transactions, so this test can't use the
rolled-back `db` fixture. It cleans up the rows it commits."""

import threading
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import Settings
from app.main import create_app
from app.services.news import get_news_provider
from app.services.news.base import NormalizedArticle, SearchParams
from app.services.news.fake import FakeNewsProvider


class SlowProvider(FakeNewsProvider):
    """Slow enough that two requests overlap inside the provider call."""

    def __init__(self) -> None:
        super().__init__()
        self.name = "gnews"
        self.calls = 0
        self._lock = threading.Lock()

    def search(self, params: SearchParams) -> list[NormalizedArticle]:
        with self._lock:
            self.calls += 1
        time.sleep(0.5)
        return super().search(params)


@pytest.fixture
def committed_tables(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        # CASCADE also clears tables that reference these (e.g. analyses).
        conn.execute(text("TRUNCATE searches, articles, search_results CASCADE"))


def test_concurrent_searches_cannot_exceed_the_daily_quota(committed_tables: None) -> None:
    provider = SlowProvider()
    app = create_app(Settings(news_daily_request_limit=1))
    app.dependency_overrides[get_news_provider] = lambda: provider
    client = TestClient(app)
    statuses: list[int] = []

    def run(q: str) -> None:
        statuses.append(client.post("/api/searches", json={"q": q}).status_code)

    threads = [threading.Thread(target=run, args=(q,)) for q in ("alpha", "beta")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert provider.calls == 1  # the quota of 1 was never exceeded
    assert sorted(statuses) == [201, 429]
