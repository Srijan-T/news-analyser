"""Keep tests hermetic: real environment variables always win over backend/.env, so pin the
ones that change app behaviour before any app code reads settings. This stops a developer's
local .env (e.g. NEWS_PROVIDER=gnews) from making tests call real APIs or use the dev DB."""

import os
from pathlib import Path

import pytest

os.environ["NEWS_PROVIDER"] = "fake"
for name in ("GNEWS_API_KEY", "APP_PASSWORD", "SESSION_SECRET", "STATIC_DIR"):
    os.environ[name] = ""

# Tests run against a separate database (created by docker-compose; a service in CI).
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://app:app@localhost:5433/news_analyser_test"
)


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Bring the test database to the latest migration once per test run, exactly as a
    deploy does. This also proves the migrations themselves apply cleanly."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    command.upgrade(config, "head")
