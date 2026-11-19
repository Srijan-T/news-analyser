from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import AppError, register_error_handlers


def make_client() -> TestClient:
    """A tiny app with routes that fail in each way the error handlers cover."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/app-error")
    def raise_app_error() -> None:
        raise AppError(502, "provider_unavailable", "News provider is down", {"provider": "x"})

    @app.get("/needs-int")
    def needs_int(n: int) -> int:
        return n

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("unexpected")

    return TestClient(app, raise_server_exceptions=False)


def test_app_error_uses_envelope() -> None:
    res = make_client().get("/app-error")
    assert res.status_code == 502
    assert res.json() == {
        "error": {
            "code": "provider_unavailable",
            "message": "News provider is down",
            "details": {"provider": "x"},
        }
    }


def test_unknown_route_returns_not_found_envelope() -> None:
    res = make_client().get("/does-not-exist")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_validation_error_lists_fields() -> None:
    res = make_client().get("/needs-int", params={"n": "abc"})
    assert res.status_code == 422
    body = res.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"][0]["field"] == "query.n"


def test_unhandled_error_hides_internals() -> None:
    res = make_client().get("/boom")
    assert res.status_code == 500
    assert res.json()["error"] == {
        "code": "internal_error",
        "message": "Something went wrong",
        "details": None,
    }
