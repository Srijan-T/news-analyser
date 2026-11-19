"""Serve the built React app from FastAPI, so production is one service on one origin."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def mount_spa(app: FastAPI, dist: Path) -> None:
    """Serve files from Vite's build output; any other non-API path gets index.html so
    client-side routes like /history survive a page refresh. Register this last so API
    routes match first."""
    root = dist.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)  # unknown API route: JSON 404, not the app
        candidate = (root / path).resolve()
        # resolve() collapses "..", so anything outside the build dir fails this check.
        if path and candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
