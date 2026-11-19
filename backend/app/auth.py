"""Sign-in for the deployed app, so strangers can't spend the news and AI API quotas.

One shared password (APP_PASSWORD). Signing in sets an HttpOnly cookie holding
"<expiry>.<HMAC-SHA256 of expiry>", signed with SESSION_SECRET, so the server needs no
session storage. The middleware guards /api/*; pages and assets stay open so the React
app can load and show its own sign-in form.
"""

import hashlib
import hmac
import time

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.errors import error_response

COOKIE_NAME = "na_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60

# Reachable without signing in: Railway's health check, and the auth endpoints themselves.
OPEN_API_PATHS = frozenset(
    {"/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/session"}
)


def _signature(secret: str, expires: int) -> str:
    return hmac.new(secret.encode(), str(expires).encode(), hashlib.sha256).hexdigest()


def sign_session(secret: str, now: float | None = None) -> str:
    expires = int(now if now is not None else time.time()) + SESSION_TTL_SECONDS
    return f"{expires}.{_signature(secret, expires)}"


def verify_session(secret: str, token: str | None, now: float | None = None) -> bool:
    if not token:
        return False
    expires_text, _, signature = token.partition(".")
    if not expires_text.isdigit():
        return False
    expires = int(expires_text)
    # compare_digest: timing doesn't reveal how much of the signature matched.
    if not hmac.compare_digest(signature, _signature(secret, expires)):
        return False
    return expires > (now if now is not None else time.time())


class SessionAuthMiddleware:
    """Pure ASGI middleware: rejects /api/* requests without a valid session cookie."""

    def __init__(self, app: ASGIApp, secret: str) -> None:
        self.app = app
        self._secret = secret

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        needs_session = (
            scope["type"] == "http" and path.startswith("/api/") and path not in OPEN_API_PATHS
        )
        if needs_session and not verify_session(
            self._secret, Request(scope).cookies.get(COOKIE_NAME)
        ):
            response = error_response(401, "unauthenticated", "Sign in to use this app")
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
