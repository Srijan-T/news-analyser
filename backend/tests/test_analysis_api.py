from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.main import create_app
from app.models import Analysis
from app.services.ai import get_analyzer
from app.services.ai.base import AnalysisError, AnalyzerResult, ArticleText
from app.services.ai.fake import FakeAnalyzer
from app.services.ai.prompts import PROMPT_VERSION
from app.services.news import get_news_provider
from app.services.news.fake import FakeNewsProvider


class CountingAnalyzer(FakeAnalyzer):
    def __init__(self) -> None:
        self.calls: list[ArticleText] = []

    def analyze(self, article: ArticleText) -> AnalyzerResult:
        self.calls.append(article)
        return super().analyze(article)


class FailingAnalyzer:
    def analyze(self, article: ArticleText) -> AnalyzerResult:
        raise AnalysisError.output_invalid()


@pytest.fixture
def analyzer() -> CountingAnalyzer:
    return CountingAnalyzer()


@pytest.fixture
def make_client(db: Session) -> Callable[[object], TestClient]:
    def make(analyzer: object) -> TestClient:
        app = create_app(Settings())
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_news_provider] = FakeNewsProvider
        app.dependency_overrides[get_analyzer] = lambda: analyzer
        return TestClient(app)

    return make


@pytest.fixture
def client(make_client: Callable[[object], TestClient], analyzer: CountingAnalyzer) -> TestClient:
    return make_client(analyzer)


def first_article_id(client: TestClient) -> int:
    search = client.post("/api/searches", json={"q": "anthropic"}).json()
    return search["items"][0]["id"]


def test_analyze_creates_and_stores_analysis(client: TestClient, db: Session) -> None:
    article_id = first_article_id(client)

    res = client.post(f"/api/articles/{article_id}/analysis")

    assert res.status_code == 201
    body = res.json()
    assert body["sentiment"] in {"positive", "neutral", "negative"}
    assert -1 <= body["score"] <= 1
    assert body["tldr"]
    assert isinstance(body["key_points"], list)
    assert isinstance(body["evidence"], list)
    # Traceability
    assert body["prompt_version"] == PROMPT_VERSION
    assert body["model"] == "fake"
    assert body["text_source"] == "snippet"
    assert db.scalar(select(func.count()).select_from(Analysis)) == 1


def test_second_analyze_returns_existing_without_calling_ai(
    client: TestClient, analyzer: CountingAnalyzer
) -> None:
    article_id = first_article_id(client)
    first = client.post(f"/api/articles/{article_id}/analysis").json()

    second = client.post(f"/api/articles/{article_id}/analysis")

    assert second.status_code == 200
    assert second.json()["id"] == first["id"]
    assert len(analyzer.calls) == 1


def test_analyzer_sees_title_description_and_snippet(
    client: TestClient, analyzer: CountingAnalyzer
) -> None:
    article_id = first_article_id(client)
    article = client.get(f"/api/articles/{article_id}").json()

    client.post(f"/api/articles/{article_id}/analysis")

    seen = analyzer.calls[0]
    assert (seen.title, seen.description, seen.snippet) == (
        article["title"],
        article["description"],
        article["snippet"],
    )


def test_article_includes_analysis_once_it_exists(client: TestClient) -> None:
    article_id = first_article_id(client)
    assert client.get(f"/api/articles/{article_id}").json()["analysis"] is None

    created = client.post(f"/api/articles/{article_id}/analysis").json()

    assert client.get(f"/api/articles/{article_id}").json()["analysis"]["id"] == created["id"]


def test_search_results_show_existing_analyses_inline(client: TestClient) -> None:
    search = client.post("/api/searches", json={"q": "anthropic"}).json()
    analyzed_id = search["items"][0]["id"]
    client.post(f"/api/articles/{analyzed_id}/analysis")

    items = client.get(f"/api/searches/{search['id']}").json()["items"]

    by_id = {item["id"]: item["analysis"] for item in items}
    assert by_id[analyzed_id] is not None
    assert all(a is None for i, a in by_id.items() if i != analyzed_id)


def test_unknown_article_is_404(client: TestClient, analyzer: CountingAnalyzer) -> None:
    for res in (client.get("/api/articles/999999"), client.post("/api/articles/999999/analysis")):
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "article_not_found"
    assert analyzer.calls == []


def test_ai_failure_returns_502_and_stores_nothing(
    make_client: Callable[[object], TestClient], db: Session
) -> None:
    client = make_client(FailingAnalyzer())
    article_id = first_article_id(client)

    res = client.post(f"/api/articles/{article_id}/analysis")

    assert res.status_code == 502
    assert res.json()["error"]["code"] == "ai_output_invalid"
    assert db.scalar(select(func.count()).select_from(Analysis)) == 0
