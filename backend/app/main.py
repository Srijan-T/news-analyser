from fastapi import FastAPI

from app.errors import register_error_handlers
from app.routers import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="News Analyser API",
        description="Search real-time news and get an AI summary and sentiment per article.",
        version="0.1.0",
    )
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    return app


app = create_app()
