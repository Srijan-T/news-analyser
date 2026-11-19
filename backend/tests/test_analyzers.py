from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest
from pydantic import ValidationError

from app.services.ai.base import AnalysisDraft, AnalysisError, ArticleText, normalize
from app.services.ai.fake import FakeAnalyzer
from app.services.ai.openai_analyzer import OpenAIAnalyzer
from app.services.ai.prompts import PROMPT_VERSION, build_input

ARTICLE = ArticleText(
    title="Acme beats forecasts as profits surge",
    description="Acme Corp reported record quarterly profits on Tuesday, lifting its shares.",
    snippet="Analysts said the results showed strong demand across every region…",
    source_name="Example News",
)


def draft(**overrides: Any) -> AnalysisDraft:
    fields: dict[str, Any] = {
        "tldr": "Acme posted record profits.",
        "key_points": ["Record quarterly profits", "Shares rose"],
        "sentiment": "positive",
        "score": 0.7,
        "rationale": "Strong results and rising shares.",
        "evidence": ["reported record quarterly profits"],
    }
    return AnalysisDraft.model_validate(fields | overrides)


class StubResponses:
    """Stands in for client.responses: returns a canned result or raises."""

    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


def make_analyzer(responses: StubResponses) -> OpenAIAnalyzer:
    client = SimpleNamespace(responses=responses)
    return OpenAIAnalyzer(client=client, model="gpt-6-luna")  # type: ignore[arg-type]


def ok_response(parsed: AnalysisDraft | None) -> object:
    return SimpleNamespace(
        output_parsed=parsed, usage=SimpleNamespace(input_tokens=321, output_tokens=87)
    )


# --- OpenAI analyzer ----------------------------------------------------------------------


def test_openai_analyzer_returns_normalized_result_with_usage() -> None:
    responses = StubResponses(result=ok_response(draft()))

    result = make_analyzer(responses).analyze(ARTICLE)

    assert result.draft.sentiment == "positive"
    assert (result.model, result.input_tokens, result.output_tokens) == ("gpt-6-luna", 321, 87)
    call = responses.calls[0]
    assert call["model"] == "gpt-6-luna"
    assert call["text_format"] is AnalysisDraft
    assert ARTICLE.title in str(call["input"])


def test_refusal_is_ai_output_invalid() -> None:
    with pytest.raises(AnalysisError) as exc_info:
        make_analyzer(StubResponses(result=ok_response(None))).analyze(ARTICLE)
    assert exc_info.value.code == "ai_output_invalid"


def test_schema_invalid_output_is_ai_output_invalid() -> None:
    with pytest.raises(ValidationError) as invalid:
        AnalysisDraft.model_validate({"tldr": "only this"})
    with pytest.raises(AnalysisError) as exc_info:
        make_analyzer(StubResponses(error=invalid.value)).analyze(ARTICLE)
    assert exc_info.value.code == "ai_output_invalid"


def test_api_failure_is_ai_unavailable() -> None:
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    with pytest.raises(AnalysisError) as exc_info:
        make_analyzer(StubResponses(error=openai.APITimeoutError(request=request))).analyze(ARTICLE)
    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "ai_unavailable"


# --- normalization (our guarantees, whatever the model returns) ---------------------------


def test_normalize_clamps_score_and_caps_lists() -> None:
    result = normalize(draft(score=3.5, key_points=["a", "b", "c", "d"], evidence=[]), ARTICLE)
    assert result.score == 1.0
    assert result.key_points == ["a", "b", "c"]


def test_normalize_drops_evidence_not_found_in_the_source_text() -> None:
    result = normalize(
        draft(
            evidence=[
                "Reported Record Quarterly Profits",  # real, different case: kept
                "the CEO resigned in disgrace",  # invented: dropped
                "lifting its shares",
            ]
        ),
        ARTICLE,
    )
    assert result.evidence == ["Reported Record Quarterly Profits", "lifting its shares"]


def test_normalize_keeps_at_most_two_evidence_quotes() -> None:
    quotes = ["record quarterly profits", "lifting its shares", "strong demand"]
    assert len(normalize(draft(evidence=quotes), ARTICLE).evidence) == 2


# --- prompt and fake ----------------------------------------------------------------------


def test_prompt_includes_all_available_text_and_has_a_version() -> None:
    text = build_input(ARTICLE)
    for part in (ARTICLE.title, ARTICLE.description, ARTICLE.snippet, ARTICLE.source_name):
        assert part and part in text
    assert PROMPT_VERSION


def test_fake_analyzer_is_deterministic_and_valid() -> None:
    first = FakeAnalyzer().analyze(ARTICLE)
    second = FakeAnalyzer().analyze(ARTICLE)

    assert first == second
    assert first.draft.sentiment == "positive"  # "surge", "record", "beats"
    assert -1 <= first.draft.score <= 1
    assert first.model == "fake"


def test_fake_analyzer_reads_negative_news_as_negative() -> None:
    bad = ArticleText(
        title="Factory fire forces layoffs",
        description="A fire destroyed the plant, and the company announced layoffs and losses.",
        snippet=None,
        source_name="Example News",
    )
    assert FakeAnalyzer().analyze(bad).draft.sentiment == "negative"
