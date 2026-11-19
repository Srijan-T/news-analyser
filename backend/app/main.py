from fastapi import FastAPI

from app.auth import SessionAuthMiddleware
from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.errors import register_error_handlers
from app.routers import auth, health, news
from app.spa import mount_spa


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.app_password and not settings.session_secret:
        raise ValueError("APP_PASSWORD is set but SESSION_SECRET is not; set both or neither")

    app = FastAPI(
        title="News Analyser API",
        description="Search real-time news and get an AI summary and sentiment per article.",
        version="0.1.0",
    )
    app.state.settings = settings
    # create_engine doesn't connect yet; the first request (or health check) does.
    app.state.session_factory = make_session_factory(make_engine(settings.database_url))
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(news.router, prefix="/api")

    if settings.static_dir:
        mount_spa(app, settings.static_dir)  # last, so API routes match first

    if settings.app_password and settings.session_secret:
        app.add_middleware(SessionAuthMiddleware, secret=settings.session_secret.get_secret_value())
    return app


app = create_app()
