"""Typo correction for search queries ("environmental improvemenets" -> "... improvements").

Only used when a search finds nothing (see services/searches.run_search). Hybrid design:
- LocalSpellCorrector (symspellpy, free, ~instant) fixes clear typos on its own;
- when it isn't confident, LLMQueryCorrector asks the model, which knows names and context
  ("nvdia" -> "nvidia", not the dictionary's "nadia").
"""

import importlib.resources
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import openai
from pydantic import BaseModel, ValidationError
from symspellpy import SymSpell, Verbosity

OPERATORS = frozenset({"AND", "OR", "NOT"})

# Calibrated against the bundled dictionary: confident only for a single-letter slip to a
# common word that clearly beats the runner-up. Anything riskier goes to the LLM.
MAX_CONFIDENT_DISTANCE = 1
MIN_CONFIDENT_COUNT = 5_000_000
MIN_LEAD_OVER_RUNNER_UP = 10


class QueryCorrector(Protocol):
    def suggest(self, query: str) -> str | None:
        """A corrected query, or None if there's nothing (confident) to change."""
        ...


@dataclass(frozen=True)
class LocalCheck:
    corrected: str | None  # None: nothing to change
    confident: bool  # False: there are unknown words it couldn't fix safely


@lru_cache
def _symspell() -> SymSpell:
    """Load the ~83k-word frequency dictionary once (about half a second)."""
    spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    dictionary = importlib.resources.files("symspellpy") / "frequency_dictionary_en_82_765.txt"
    spell.load_dictionary(str(dictionary), term_index=0, count_index=1)
    return spell


class LocalSpellCorrector:
    def check(self, query: str) -> LocalCheck:
        spell = _symspell()
        confident = True
        words: list[str] = []
        for token in query.split():
            fixed = self._fix_word(spell, token)
            if fixed is None:
                confident = False
                words.append(token)
            else:
                words.append(fixed)
        corrected = " ".join(words)
        return LocalCheck(
            corrected=None if corrected == " ".join(query.split()) else corrected,
            confident=confident,
        )

    def suggest(self, query: str) -> str | None:
        check = self.check(query)
        return check.corrected if check.confident else None

    @staticmethod
    def _fix_word(spell: SymSpell, token: str) -> str | None:
        """The word to use, or None if it's unknown and can't be fixed confidently."""
        # Leave alone: operators, names (capitalized), and anything that isn't a plain word
        # (quotes, numbers, hyphens), which we can't safely rewrite.
        if token in OPERATORS or token[:1].isupper() or not re.fullmatch(r"[a-z']+", token):
            return token
        if token in spell.words:
            return token
        candidates = spell.lookup(token, Verbosity.CLOSEST, max_edit_distance=2)
        if not candidates:
            return None
        best = candidates[0]
        runner_up = candidates[1].count if len(candidates) > 1 else 0
        if (
            best.distance <= MAX_CONFIDENT_DISTANCE
            and best.count >= MIN_CONFIDENT_COUNT
            and best.count >= MIN_LEAD_OVER_RUNNER_UP * runner_up
        ):
            return best.term
        return None


class QueryCorrection(BaseModel):
    """Structured Outputs schema for the LLM: null when the query needs no change."""

    corrected_query: str | None


CORRECTION_PROMPT = """You fix typos in news search queries.
Return the query with spelling mistakes corrected, keeping its meaning, word order and any
names (companies, people, places), which you should spell correctly (e.g. "nvdia" -> "nvidia").
Do not add, remove or rephrase words. If nothing is misspelled, return null."""


class LLMQueryCorrector:
    def __init__(self, client: openai.OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def suggest(self, query: str) -> str | None:
        try:
            response = self._client.responses.parse(
                model=self._model,
                input=[
                    {"role": "system", "content": CORRECTION_PROMPT},
                    {"role": "user", "content": query},
                ],
                text_format=QueryCorrection,
            )
        except (openai.APIError, ValidationError):
            return None  # correction is a nice-to-have: never fail the search over it
        parsed = response.output_parsed
        corrected = (parsed.corrected_query or "").strip() if parsed else ""
        if not corrected or corrected.lower() == query.strip().lower():
            return None
        return corrected[:200]  # same limit as user queries


class HybridCorrector:
    def __init__(self, local: LocalSpellCorrector, llm: QueryCorrector | None) -> None:
        self._local = local
        self._llm = llm

    def suggest(self, query: str) -> str | None:
        check = self._local.check(query)
        if check.confident:
            return check.corrected
        # The local guess was risky; only the LLM may decide. Without one, change nothing.
        return self._llm.suggest(query) if self._llm else None


CORRECTION_TIMEOUT_SECONDS = 8.0  # a correction is a nice-to-have; don't hold a search long


@lru_cache
def get_query_corrector() -> QueryCorrector:
    """FastAPI dependency. With ANALYZER=fake (dev, CI) only the free local checker runs, so
    no tokens are spent; with the OpenAI analyzer configured, unsure cases go to the model."""
    from app.config import get_settings  # local import: avoid a cycle at module import time

    settings = get_settings()
    key = settings.openai_api_key.get_secret_value().strip() if settings.openai_api_key else ""
    llm: QueryCorrector | None = None
    if settings.analyzer == "openai" and key:
        client = openai.OpenAI(api_key=key, timeout=CORRECTION_TIMEOUT_SECONDS, max_retries=1)
        llm = LLMQueryCorrector(client=client, model=settings.openai_model)
    return HybridCorrector(LocalSpellCorrector(), llm)
