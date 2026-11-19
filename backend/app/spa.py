"""Serve the built React app from FastAPI, so production is one service on one origin."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.convertors import Convertor, register_url_convertor


class NonApiPathConvertor(Convertor[str]):
    """Like `{path:path}`, but never matches /api or /api/...

    Because the SPA route can't match API paths at all, they keep Starlette's normal
    behaviour: trailing-slash redirects, JSON 404 for unknown routes, 405 for wrong methods.
    """

    regex = r"(?!api(?:/|$)).*"

    def convert(self, value: str) -> str:
        return value

    def to_string(self, value: str) -> str:
        return value


register_url_convertor("non_api_path", NonApiPathConvertor())


def mount_spa(app: FastAPI, dist: Path) -> None:
    """Serve files from Vite's build output; any other non-API path gets index.html so
    client-side routes like /history survive a page refresh. Register this last so API
    routes match first."""
    root = dist.resolve()
    index = root / "index.html"

    @app.get("/{path:non_api_path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (root / path).resolve()
        # resolve() collapses "..", so anything outside the build dir fails this check.
        if path and candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
