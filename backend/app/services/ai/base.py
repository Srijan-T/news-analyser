"""What an analysis is, and the interface every analyzer (OpenAI, fake) implements."""

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel

from app.errors import AppError

Sentiment = Literal["positive", "neutral", "negative"]

MAX_KEY_POINTS = 3
MAX_EVIDENCE = 2


class AnalysisDraft(BaseModel):
    """The JSON schema sent to the model (Structured Outputs).

    Kept to plain types and an enum, which strict mode supports everywhere. Limits on
    counts and ranges are enforced afterwards by `normalize`, not trusted to the model.
    """

    tldr: str
    key_points: list[str]
    sentiment: Sentiment
    score: float
    rationale: str
    evidence: list[str]


@dataclass(frozen=True)
class ArticleText:
    """Everything the analyzer may read about an article."""

    title: str
    description: str | None
    snippet: str | None
    source_name: str

    @property
    def body(self) -> str:
        return "\n".join(part for part in (self.title, self.description, self.snippet) if part)


@dataclass(frozen=True)
class AnalyzerResult:
    draft: AnalysisDraft
    model: str
    input_tokens: int | None
    output_tokens: int | None


class Analyzer(Protocol):
    def analyze(self, article: ArticleText) -> AnalyzerResult: ...


class AnalysisError(AppError):
    @classmethod
    def output_invalid(cls) -> "AnalysisError":
        return cls(502, "ai_output_invalid", "The AI couldn't produce an analysis. Try again.")

    @classmethod
    def unavailable(cls) -> "AnalysisError":
        return cls(502, "ai_unavailable", "The AI service is unavailable. Try again shortly.")

    @classmethod
    def not_configured(cls) -> "AnalysisError":
        return cls(500, "ai_not_configured", "ANALYZER=openai but OPENAI_API_KEY is not set")


def normalize(draft: AnalysisDraft, article: ArticleText) -> AnalysisDraft:
    """Enforce our guarantees whatever the model returned: score in [-1, 1], at most 3 key
    points, and at most 2 evidence quotes that really appear in the article text (so the UI
    never shows an invented quote)."""
    source = " ".join(article.body.lower().split())
    evidence = [
        quote.strip()
        for quote in draft.evidence
        if quote.strip() and " ".join(quote.lower().split()) in source
    ]
    return draft.model_copy(
        update={
            "score": max(-1.0, min(1.0, draft.score)),
            "key_points": [p.strip() for p in draft.key_points if p.strip()][:MAX_KEY_POINTS],
            "evidence": evidence[:MAX_EVIDENCE],
        }
    )
