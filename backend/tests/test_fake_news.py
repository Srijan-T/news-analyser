from app.services.news.base import SearchParams
from app.services.news.fake import FakeNewsProvider


def test_matching_query_filters_articles() -> None:
    results = FakeNewsProvider().search(SearchParams(q="anthropic"))

    assert results
    assert all("anthropic" in f"{a.title} {a.description}".lower() for a in results)
    assert all(a.provider == "fake" for a in results)


def test_unmatched_query_returns_nothing_like_the_real_api() -> None:
    assert FakeNewsProvider().search(SearchParams(q="zzz-no-match")) == []


def test_or_matches_any_group() -> None:
    either = FakeNewsProvider().search(SearchParams(q="zzz-no-match OR anthropic"))
    assert either
    assert all("anthropic" in f"{a.title} {a.description}".lower() for a in either)


def test_latest_sort_is_newest_first() -> None:
    results = FakeNewsProvider().search(SearchParams(q="openai", sort="latest"))
    dates = [a.published_at for a in results]
    assert dates == sorted(dates, reverse=True)
