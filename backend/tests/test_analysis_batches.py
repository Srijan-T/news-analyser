"""Batch analysis: POST a set of article ids, a background job analyzes them, GET polls it."""

import threading
from collections.abc import Callable, Iterator
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.main import create_app
from app.models import Analysis, AnalysisBatchItem
from app.services.ai import get_analyzer
from app.services.ai.base import AnalysisError, AnalyzerResult, ArticleText
from app.services.ai.fake import FakeAnalyzer
from app.services.batches import BatchRunner, get_batch_runner
from app.services.news import get_news_provider
from app.services.news.fake import FakeNewsProvider


class CountingAnalyzer(FakeAnalyzer):
    """Records every call; fails for titles listed in `fail_titles`."""

    def __init__(self, fail_titles: frozenset[str] = frozenset()) -> None:
        self.calls: list[str] = []
        self.fail_titles = fail_titles
        self._lock = threading.Lock()

    def analyze(self, article: ArticleText) -> AnalyzerResult:
        with self._lock:
            self.calls.append(article.title)
        if article.title in self.fail_titles:
            raise AnalysisError.unavailable()
        return super().analyze(article)


MakeClient = Callable[[CountingAnalyzer], TestClient]


@pytest.fixture
def make_client(db: Session) -> MakeClient:
    def make(analyzer: CountingAnalyzer) -> TestClient:
        app = create_app(Settings())
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_news_provider] = FakeNewsProvider
        app.dependency_overrides[get_analyzer] = lambda: analyzer
        # One worker on the test session: the same code path as production, run inline.
        app.dependency_overrides[get_batch_runner] = lambda: BatchRunner(
            open_session=lambda: nullcontext(db), analyzer=analyzer, workers=1
        )
        return TestClient(app)

    return make


def article_ids(client: TestClient, q: str = "AI") -> list[int]:
    return [a["id"] for a in client.post("/api/searches", json={"q": q}).json()["items"]]


def start(client: TestClient, ids: list[int]):
    return client.post("/api/analysis-batches", json={"article_ids": ids})


def test_batch_analyzes_every_article(make_client: MakeClient, db: Session) -> None:
    analyzer = CountingAnalyzer()
    client = make_client(analyzer)
    ids = article_ids(client)[:3]

    res = start(client, ids)

    assert res.status_code == 202
    batch_id = res.json()["id"]
    assert res.headers["location"] == f"/api/analysis-batches/{batch_id}"
    # TestClient runs background tasks before returning, so the job is finished here.
    batch = client.get(f"/api/analysis-batches/{batch_id}").json()
    assert batch["status"] == "done"
    assert [i["article_id"] for i in batch["items"]] == ids  # in the order requested
    assert {i["status"] for i in batch["items"]} == {"done"}
    assert batch["counts"] == {"pending": 0, "running": 0, "done": 3, "skipped": 0, "failed": 0}
    assert len(analyzer.calls) == 3
    assert db.scalar(select(func.count()).select_from(Analysis)) == 3


def test_already_analyzed_articles_are_skipped(make_client: MakeClient) -> None:
    analyzer = CountingAnalyzer()
    client = make_client(analyzer)
    first, second = article_ids(client)[:2]
    client.post(f"/api/articles/{first}/analysis")

    batch_id = start(client, [first, second]).json()["id"]
    batch = client.get(f"/api/analysis-batches/{batch_id}").json()

    assert [(i["article_id"], i["status"]) for i in batch["items"]] == [
        (first, "skipped"),
        (second, "done"),
    ]
    assert len(analyzer.calls) == 2  # one single analysis + one in the batch


def test_a_failure_does_not_stop_the_rest(make_client: MakeClient) -> None:
    client = make_client(CountingAnalyzer())
    items = client.post("/api/searches", json={"q": "AI"}).json()["items"][:3]
    failing = CountingAnalyzer(fail_titles=frozenset({items[1]["title"]}))
    client = make_client(failing)

    batch_id = start(client, [a["id"] for a in items]).json()["id"]
    batch = client.get(f"/api/analysis-batches/{batch_id}").json()

    assert batch["status"] == "done"
    assert [(i["status"], i["error_code"]) for i in batch["items"]] == [
        ("done", None),
        ("failed", "ai_unavailable"),
        ("done", None),
    ]


def test_response_includes_finished_analyses(make_client: MakeClient) -> None:
    client = make_client(CountingAnalyzer())
    ids = article_ids(client)[:1]

    batch = client.get(f"/api/analysis-batches/{start(client, ids).json()['id']}").json()

    assert batch["items"][0]["analysis"]["sentiment"] in {"positive", "neutral", "negative"}


@pytest.mark.parametrize(
    "ids",
    [[], list(range(1, 12)), [1, 1]],
    ids=["empty", "more-than-10", "duplicates"],
)
def test_invalid_id_lists_are_rejected(make_client: MakeClient, ids: list[int]) -> None:
    res = start(make_client(CountingAnalyzer()), ids)

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_unknown_article_ids_give_404_and_create_nothing(
    make_client: MakeClient, db: Session
) -> None:
    client = make_client(CountingAnalyzer())
    known = article_ids(client)[0]

    res = start(client, [known, 999_999_999])

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "article_not_found"
    assert res.json()["error"]["details"] == {"missing_ids": [999_999_999]}
    assert db.scalar(select(func.count()).select_from(AnalysisBatchItem)) == 0


def test_unknown_batch_gives_404(make_client: MakeClient) -> None:
    res = make_client(CountingAnalyzer()).get("/api/analysis-batches/999999999")

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "batch_not_found"


def test_items_stuck_for_too_long_are_reported_as_interrupted(
    make_client: MakeClient, db: Session
) -> None:
    """If the server restarts mid-batch, its in-memory job is gone: report the leftovers as
    failed instead of leaving the batch "running" forever."""
    client = make_client(CountingAnalyzer())
    batch_id = start(client, article_ids(client)[:2]).json()["id"]
    old = datetime.now(UTC) - timedelta(minutes=11)
    db.execute(
        update(AnalysisBatchItem)
        .where(AnalysisBatchItem.batch_id == batch_id)
        .values(status="running", updated_at=old)
    )

    batch = client.get(f"/api/analysis-batches/{batch_id}").json()

    assert batch["status"] == "done"
    assert {(i["status"], i["error_code"]) for i in batch["items"]} == {("failed", "interrupted")}


def test_recent_running_items_keep_the_batch_running(make_client: MakeClient, db: Session) -> None:
    client = make_client(CountingAnalyzer())
    batch_id = start(client, article_ids(client)[:2]).json()["id"]
    db.execute(
        update(AnalysisBatchItem)
        .where(AnalysisBatchItem.batch_id == batch_id)
        .values(status="pending")
    )

    batch = client.get(f"/api/analysis-batches/{batch_id}").json()

    assert batch["status"] == "running"
    assert batch["counts"]["pending"] == 2


# --- Real threads and commits: can't use the rolled-back `db` fixture -----------------------


@pytest.fixture
def committed_tables(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE searches, articles, search_results, analysis_batches CASCADE"))


def test_parallel_workers_analyze_each_article_once(committed_tables: None) -> None:
    analyzer = CountingAnalyzer()
    app = create_app(Settings())
    app.dependency_overrides[get_news_provider] = FakeNewsProvider
    app.dependency_overrides[get_analyzer] = lambda: analyzer
    client = TestClient(app)  # the real runner: 3 threads, a session each
    ids = article_ids(client)[:5]

    batch_id = start(client, ids).json()["id"]
    batch = client.get(f"/api/analysis-batches/{batch_id}").json()

    assert batch["status"] == "done"
    assert {i["status"] for i in batch["items"]} == {"done"}
    assert len(analyzer.calls) == 5  # 5 articles, all done: none analyzed twice
