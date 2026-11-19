import pytest

from app.config import Settings


@pytest.mark.parametrize(
    "given",
    [
        "postgres://u:p@host:5432/db",  # Heroku/Railway-style scheme
        "postgresql://u:p@host:5432/db",  # what Railway's DATABASE_URL uses
        "postgresql+psycopg://u:p@host:5432/db",  # already explicit: unchanged
    ],
)
def test_database_url_uses_the_psycopg_driver(given: str) -> None:
    assert Settings(database_url=given).database_url == "postgresql+psycopg://u:p@host:5432/db"
