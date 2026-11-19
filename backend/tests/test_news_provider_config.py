import pytest

from app.config import Settings
from app.errors import AppError
from app.services import news
from app.services.news.gnews import GNewsProvider


def provider_for(monkeypatch: pytest.MonkeyPatch, **settings: object):
    monkeypatch.setattr(news, "get_settings", lambda: Settings.model_validate(settings))
    # get_news_provider is lru_cached; call the undecorated function so each test is fresh.
    return news.get_news_provider.__wrapped__()


@pytest.mark.parametrize("key", [None, "", "   "])
def test_gnews_without_a_key_is_not_configured(
    monkeypatch: pytest.MonkeyPatch, key: str | None
) -> None:
    with pytest.raises(AppError) as exc_info:
        provider_for(monkeypatch, news_provider="gnews", gnews_api_key=key)

    assert exc_info.value.code == "news_provider_not_configured"


def test_gnews_with_a_key_builds_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = provider_for(monkeypatch, news_provider="gnews", gnews_api_key="abc123")

    assert isinstance(provider, GNewsProvider)
