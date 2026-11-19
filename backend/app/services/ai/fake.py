"""Offline analyzer for local dev, demos and tests: deterministic, free, no network.

It counts a few positive and negative words. Crude, but it exercises every code path with
realistic-looking output, so the UI can be built and tested without spending OpenAI tokens.
"""

import re

from app.services.ai.base import AnalysisDraft, AnalyzerResult, ArticleText, normalize

POSITIVE = {
    "beat",
    "beats",
    "surge",
    "surges",
    "record",
    "growth",
    "win",
    "wins",
    "gain",
    "gains",
    "rise",
    "rises",
    "strong",
    "boost",
    "success",
    "lifting",
    "approve",
}
NEGATIVE = {
    "fire",
    "layoffs",
    "loss",
    "losses",
    "fall",
    "falls",
    "crash",
    "lawsuit",
    "fraud",
    "cut",
    "cuts",
    "decline",
    "warning",
    "crisis",
    "dead",
    "destroyed",
    "probe",
}


class FakeAnalyzer:
    model = "fake"

    def analyze(self, article: ArticleText) -> AnalyzerResult:
        words = re.findall(r"[a-z']+", article.body.lower())
        balance = sum(w in POSITIVE for w in words) - sum(w in NEGATIVE for w in words)
        score = max(-1.0, min(1.0, balance / 3))
        sentiment = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", article.body) if s.strip()]
        evidence_source = article.description or article.title
        draft = AnalysisDraft(
            tldr=sentences[0] if sentences else article.title,
            key_points=sentences[1:4] or [article.title],
            sentiment=sentiment,
            score=round(score, 2),
            rationale=f"Keyword tone: {balance:+d} (fake analyzer, for development).",
            evidence=[" ".join(evidence_source.split()[:12])],
        )
        return AnalyzerResult(
            draft=normalize(draft, article), model=self.model, input_tokens=None, output_tokens=None
        )
