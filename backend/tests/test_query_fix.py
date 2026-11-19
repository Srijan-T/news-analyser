from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from app.services.query_fix import (
    HybridCorrector,
    LLMQueryCorrector,
    LocalSpellCorrector,
    QueryCorrection,
)

local = LocalSpellCorrector()


# --- local spell-checker ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("environmental improvemenets", "environmental improvements"),
        ("goverment econmy", "government economy"),
        ("climte policy", "climate policy"),  # clime is far rarer than climate
    ],
)
def test_local_fixes_clear_typos_confidently(query: str, expected: str) -> None:
    check = local.check(query)
    assert check.confident
    assert check.corrected == expected


@pytest.mark.parametrize(
    "query",
    [
        "climate policy",  # nothing to fix
        "Nvidia earnings",  # capitalized words are treated as names and left alone
        "climate OR election",  # search operators are left alone
    ],
)
def test_local_leaves_correct_queries_alone(query: str) -> None:
    check = local.check(query)
    assert check.confident
    assert check.corrected is None


@pytest.mark.parametrize(
    "query",
    [
        "nvdia earnings",  # closest word is the rare name "nadia": don't guess
        "electon results",  # election vs electron: too close to call
        "tarrifs news",  # only distance-2 matches ("harris"): too risky
    ],
)
def test_local_is_unsure_about_risky_corrections(query: str) -> None:
    assert not local.check(query).confident


def test_local_never_rewrites_an_unknown_brand_it_cannot_verify() -> None:
    check = local.check("openai news")  # not in the dictionary; nearest is "open"
    assert not check.confident  # so the LLM decides
    assert check.corrected is None  # and the local checker changed nothing


# --- LLM corrector ------------------------------------------------------------------------


class StubResponses:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


def llm_with(responses: StubResponses) -> LLMQueryCorrector:
    return LLMQueryCorrector(client=SimpleNamespace(responses=responses), model="m")  # type: ignore[arg-type]


def parsed(corrected: str | None) -> object:
    return SimpleNamespace(output_parsed=QueryCorrection(corrected_query=corrected))


def test_llm_returns_its_correction() -> None:
    responses = StubResponses(result=parsed("nvidia earnings"))
    assert llm_with(responses).suggest("nvdia earnings") == "nvidia earnings"
    assert responses.calls[0]["text_format"] is QueryCorrection


@pytest.mark.parametrize("answer", [None, "nvdia earnings", "  "])
def test_llm_no_change_means_none(answer: str | None) -> None:
    assert llm_with(StubResponses(result=parsed(answer))).suggest("nvdia earnings") is None


def test_llm_failure_means_none_not_an_error() -> None:
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    responses = StubResponses(error=openai.APITimeoutError(request=request))
    assert llm_with(responses).suggest("nvdia earnings") is None


def test_llm_refusal_means_none() -> None:
    responses = StubResponses(result=SimpleNamespace(output_parsed=None))
    assert llm_with(responses).suggest("nvdia earnings") is None


# --- hybrid -------------------------------------------------------------------------------


class CountingLLM:
    def __init__(self, answer: str | None) -> None:
        self.answer = answer
        self.calls: list[str] = []

    def suggest(self, query: str) -> str | None:
        self.calls.append(query)
        return self.answer


def test_hybrid_uses_local_when_confident_without_calling_the_llm() -> None:
    llm = CountingLLM("should not be used")
    assert HybridCorrector(local, llm).suggest("enviromental news") == "environmental news"
    assert llm.calls == []


def test_hybrid_asks_the_llm_when_local_is_unsure() -> None:
    llm = CountingLLM("nvidia earnings")
    assert HybridCorrector(local, llm).suggest("nvdia earnings") == "nvidia earnings"
    assert llm.calls == ["nvdia earnings"]


def test_hybrid_without_llm_never_applies_an_unsure_guess() -> None:
    assert HybridCorrector(local, None).suggest("nvdia earnings") is None


def test_dev_and_ci_corrector_never_calls_the_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import config
    from app.services import query_fix

    monkeypatch.setattr(config, "get_settings", lambda: config.Settings(analyzer="fake"))
    corrector = query_fix.get_query_corrector.__wrapped__()

    assert isinstance(corrector, HybridCorrector)
    assert corrector._llm is None  # pyright: ignore[reportPrivateUsage]
