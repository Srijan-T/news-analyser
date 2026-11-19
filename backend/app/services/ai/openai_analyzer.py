"""OpenAI analyzer: one Structured Outputs call that returns an AnalysisDraft."""

import openai
from pydantic import ValidationError

from app.services.ai.base import (
    AnalysisDraft,
    AnalysisError,
    AnalyzerResult,
    ArticleText,
    normalize,
)
from app.services.ai.prompts import SYSTEM_PROMPT, build_input


class OpenAIAnalyzer:
    def __init__(self, client: openai.OpenAI, model: str) -> None:
        self._client = client
        self.model = model

    def analyze(self, article: ArticleText) -> AnalyzerResult:
        try:
            # The SDK already retries connection errors, 429s and 5xx (2 retries by default).
            response = self._client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_input(article)},
                ],
                text_format=AnalysisDraft,
            )
        except ValidationError as exc:  # the model returned JSON that doesn't fit the schema
            raise AnalysisError.output_invalid() from exc
        except openai.APIError as exc:  # timeouts, connection errors, API errors
            raise AnalysisError.unavailable() from exc

        draft = response.output_parsed
        if draft is None:  # refusal, or no final answer
            raise AnalysisError.output_invalid()

        usage = response.usage
        return AnalyzerResult(
            draft=normalize(draft, article),
            model=self.model,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
        )
