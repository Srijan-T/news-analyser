"""Offline provider backed by a saved GNews response. Used for local dev, demos and tests,
so routine work spends none of the 100 requests/day quota."""

import json
from pathlib import Path

from app.services.news.base import NormalizedArticle, SearchParams
from app.services.news.gnews import normalize

FIXTURE = Path(__file__).parent / "fixtures" / "gnews_search.json"


class FakeNewsProvider:
    name = "fake"

    def __init__(self, fixture: Path = FIXTURE) -> None:
        raw = json.loads(fixture.read_text())
        self._articles = [normalize(a) for a in raw["articles"]]

    def search(self, params: SearchParams) -> list[NormalizedArticle]:
        words = params.q.lower().split()
        matches = [
            a
            for a in self._articles
            if all(w in f"{a.title} {a.description or ''}".lower() for w in words)
        ]
        # The fixture is small, so an unmatched query returns everything rather than nothing.
        results = matches or self._articles
        if params.sort == "latest":
            results = sorted(results, key=lambda a: a.published_at, reverse=True)
        return [a.model_copy(update={"provider": self.name}) for a in results]
