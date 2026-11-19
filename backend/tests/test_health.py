from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, create_app


def test_health_reports_app_and_database_ok() -> None:
    res = TestClient(app).get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": "ok"}


def test_health_is_503_when_database_is_unreachable() -> None:
    # Nothing listens on port 1, so the connection is refused immediately.
    settings = Settings(database_url="postgresql+psycopg://app:app@localhost:1/nope")
    res = TestClient(create_app(settings)).get("/api/health")

    assert res.status_code == 503
    assert res.json()["error"]["code"] == "database_unavailable"
