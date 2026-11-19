"""HTTP basic auth for the deployed app, so strangers can't spend the API quotas.

Pure ASGI middleware (rather than a route dependency) so it also covers the static frontend
and /docs, not just API routes.
"""

import base64
import binascii
import secrets

from starlette.types import ASGIApp, Receive, Scope, Send

from app.errors import error_response

# Railway's health check can't send credentials.
OPEN_PATHS = frozenset({"/api/health"})


class BasicAuthMiddleware:
    def __init__(self, app: ASGIApp, username: str, password: str) -> None:
        self.app = app
        self._username = username.encode()
        self._password = password.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in OPEN_PATHS or self._authorized(scope):
            await self.app(scope, receive, send)
            return
        response = error_response(401, "unauthorized", "Sign in to use this app")
        response.headers["WWW-Authenticate"] = 'Basic realm="News Analyser", charset="UTF-8"'
        await response(scope, receive, send)

    def _authorized(self, scope: Scope) -> bool:
        header = dict(scope["headers"]).get(b"authorization", b"")
        scheme, _, token = header.partition(b" ")
        if scheme.lower() != b"basic":
            return False
        try:
            user, _, password = base64.b64decode(token, validate=True).partition(b":")
        except (binascii.Error, ValueError):
            return False
        # compare_digest takes the same time whether the first or last byte differs,
        # so response timing can't be used to guess the password byte by byte.
        user_ok = secrets.compare_digest(user, self._username)
        password_ok = secrets.compare_digest(password, self._password)
        return user_ok and password_ok
