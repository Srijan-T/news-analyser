from fastapi import FastAPI

from app.auth import BasicAuthMiddleware
from app.config import Settings, get_settings
from app.errors import register_error_handlers
from app.routers import health, news
from app.spa import mount_spa


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="News Analyser API",
        description="Search real-time news and get an AI summary and sentiment per article.",
        version="0.1.0",
    )
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(news.router, prefix="/api")

    if settings.static_dir:
        mount_spa(app, settings.static_dir)  # last, so API routes match first

    if settings.basic_auth_user and settings.basic_auth_password:
        app.add_middleware(
            BasicAuthMiddleware,
            username=settings.basic_auth_user,
            password=settings.basic_auth_password.get_secret_value(),
        )
    return app


app = create_app()
