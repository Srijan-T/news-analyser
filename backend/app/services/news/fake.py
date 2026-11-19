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
        articles = (normalize(a) for a in raw["articles"])
        self._articles = [a for a in articles if a is not None]

    def search(self, params: SearchParams) -> list[NormalizedArticle]:
        """Like GNews: every word must match, or any group separated by OR. Unmatched queries
        return nothing, so the zero-result path (and its fallbacks) shows up in dev too."""
        groups = [g.lower().replace('"', "").split() for g in params.q.split(" OR ")]
        results = [
            a
            for a in self._articles
            if any(
                all(w in f"{a.title} {a.description or ''}".lower() for w in words)
                for words in groups
            )
        ]
        if params.sort == "latest":
            results = sorted(results, key=lambda a: a.published_at, reverse=True)
        return [a.model_copy(update={"provider": self.name}) for a in results]
