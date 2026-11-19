from functools import lru_cache

import openai

from app.config import get_settings
from app.services.ai.base import AnalysisError, Analyzer
from app.services.ai.fake import FakeAnalyzer
from app.services.ai.openai_analyzer import OpenAIAnalyzer

ANALYSIS_TIMEOUT_SECONDS = 30.0


@lru_cache
def get_analyzer() -> Analyzer:
    """FastAPI dependency: the analyzer picked by ANALYZER. Tests override this."""
    settings = get_settings()
    if settings.analyzer == "fake":
        return FakeAnalyzer()
    api_key = settings.openai_api_key.get_secret_value().strip() if settings.openai_api_key else ""
    if not api_key:
        raise AnalysisError.not_configured()
    client = openai.OpenAI(api_key=api_key, timeout=ANALYSIS_TIMEOUT_SECONDS)
    return OpenAIAnalyzer(client=client, model=settings.openai_model)
