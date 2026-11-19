import pytest
from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, sign_session
from app.config import Settings
from app.main import create_app

PASSWORD = "correct horse"
SECRET = "test-session-secret"
PROTECTED = "/api/searches"


def make_client(**overrides: object) -> TestClient:
    settings = Settings.model_validate(
        {"app_password": PASSWORD, "session_secret": SECRET} | overrides
    )
    return TestClient(create_app(settings))


@pytest.fixture
def client() -> TestClient:
    return make_client()


def login(client: TestClient, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"password": password})


# --- protection ---------------------------------------------------------------------------


def test_api_requires_sign_in(client: TestClient) -> None:
    res = client.get(PROTECTED)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthenticated"
    assert "WWW-Authenticate" not in res.headers  # no browser pop-up; the app shows a form


def test_health_and_session_are_open(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/auth/session").json() == {
        "auth_required": True,
        "authenticated": False,
    }


def test_auth_is_off_when_no_password_configured() -> None:
    client = TestClient(create_app(Settings()))
    assert client.get(PROTECTED).status_code == 200
    assert client.get("/api/auth/session").json() == {
        "auth_required": False,
        "authenticated": True,
    }


def test_password_without_session_secret_fails_fast() -> None:
    with pytest.raises(ValueError, match="SESSION_SECRET"):
        create_app(Settings.model_validate({"app_password": PASSWORD}))


# --- login / logout -----------------------------------------------------------------------


def test_correct_password_signs_in(client: TestClient) -> None:
    res = login(client)

    assert res.status_code == 204
    cookie = res.headers["set-cookie"]
    assert f"{COOKIE_NAME}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert client.get(PROTECTED).status_code == 200
    assert client.get("/api/auth/session").json()["authenticated"] is True


def test_wrong_password_is_rejected(client: TestClient) -> None:
    res = login(client, "nope")

    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_password"
    assert "set-cookie" not in res.headers
    assert client.get(PROTECTED).status_code == 401


def test_logout_clears_session(client: TestClient) -> None:
    login(client)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get(PROTECTED).status_code == 401


def test_cookie_is_secure_in_production() -> None:
    client = make_client(app_env="production")
    assert "Secure" in login(client).headers["set-cookie"]


# --- token integrity ----------------------------------------------------------------------


def test_tampered_cookie_is_rejected(client: TestClient) -> None:
    token = sign_session(SECRET, now=1_000)
    expires, _, signature = token.partition(".")
    forged = f"{int(expires) + 10_000_000}.{signature}"  # extend expiry, keep old signature
    client.cookies.set(COOKIE_NAME, forged)
    assert client.get(PROTECTED).status_code == 401


def test_cookie_signed_with_other_secret_is_rejected(client: TestClient) -> None:
    client.cookies.set(COOKIE_NAME, sign_session("some-other-secret"))
    assert client.get(PROTECTED).status_code == 401


def test_expired_cookie_is_rejected(client: TestClient) -> None:
    client.cookies.set(COOKIE_NAME, sign_session(SECRET, now=0))  # expired long ago
    assert client.get(PROTECTED).status_code == 401


@pytest.mark.parametrize("value", ["", "garbage", "123", "abc.def", ".", "1.2.3"])
def test_malformed_cookie_is_rejected(client: TestClient, value: str) -> None:
    client.cookies.set(COOKIE_NAME, value)
    assert client.get(PROTECTED).status_code == 401


def test_failed_login_delay_does_not_block_a_worker_thread(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """time.sleep in a sync route holds one of FastAPI's shared worker threads, so parallel
    wrong guesses could stall every other request. The delay must be awaited instead."""

    def blocking_sleep(_: float) -> None:
        raise AssertionError("failed login used blocking time.sleep")

    monkeypatch.setattr("time.sleep", blocking_sleep)

    assert login(client, "nope").status_code == 401
