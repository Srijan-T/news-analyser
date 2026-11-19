from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    """A fake Vite build output."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app shell</html>")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log('app')")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    (tmp_path.parent / "secret.txt").write_text("outside the build dir")
    return tmp_path


@pytest.fixture
def client(dist: Path) -> TestClient:
    return TestClient(create_app(Settings(static_dir=dist)))


def test_root_serves_index(client: TestClient) -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert "app shell" in res.text


def test_client_side_routes_fall_back_to_index(client: TestClient) -> None:
    res = client.get("/history")
    assert res.status_code == 200
    assert "app shell" in res.text


def test_built_files_are_served(client: TestClient) -> None:
    assert client.get("/assets/index-abc123.js").text == "console.log('app')"
    assert client.get("/favicon.svg").text == "<svg/>"


def test_unknown_api_route_is_json_404_not_index(client: TestClient) -> None:
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_trailing_slash_api_path_redirects_like_without_spa(client: TestClient) -> None:
    res = client.get("/api/news/search/", params={"q": "ai"}, follow_redirects=False)

    assert res.status_code == 307
    assert res.headers["location"].endswith("/api/news/search?q=ai")


def test_wrong_method_on_api_route_is_405_not_spa(client: TestClient) -> None:
    res = client.post("/api/news/search")

    assert res.status_code == 405


def test_api_routes_still_work(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_path_traversal_cannot_escape_build_dir(client: TestClient) -> None:
    res = client.get("/..%2Fsecret.txt")
    assert "outside the build dir" not in res.text


def test_no_static_dir_means_no_spa_routes() -> None:
    client = TestClient(create_app(Settings(static_dir=None)))
    assert client.get("/").status_code == 404
