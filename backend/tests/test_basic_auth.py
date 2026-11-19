import base64

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def auth_header(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def client() -> TestClient:
    settings = Settings(basic_auth_user="reviewer", basic_auth_password="s3cret")  # type: ignore[arg-type]
    return TestClient(create_app(settings))


PROTECTED = "/openapi.json"


def test_request_without_credentials_is_challenged(client: TestClient) -> None:
    res = client.get(PROTECTED)
    assert res.status_code == 401
    assert res.headers["WWW-Authenticate"].startswith("Basic")
    assert res.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    "header",
    [
        auth_header("reviewer", "wrong"),
        auth_header("someone", "s3cret"),
        {"Authorization": "Basic not-base64!!"},
        {"Authorization": "Bearer s3cret"},
    ],
)
def test_bad_credentials_are_rejected(client: TestClient, header: dict[str, str]) -> None:
    assert client.get(PROTECTED, headers=header).status_code == 401


def test_correct_credentials_pass(client: TestClient) -> None:
    res = client.get(PROTECTED, headers=auth_header("reviewer", "s3cret"))
    assert res.status_code == 200


def test_health_is_open_for_platform_health_checks(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200


def test_auth_is_off_when_not_configured() -> None:
    client = TestClient(create_app(Settings()))
    assert client.get(PROTECTED).status_code == 200


def test_auth_is_off_when_only_user_is_set() -> None:
    client = TestClient(create_app(Settings(basic_auth_user="reviewer")))  # type: ignore[arg-type]
    assert client.get(PROTECTED).status_code == 200
