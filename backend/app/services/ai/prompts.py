"""The analysis prompt. Bump PROMPT_VERSION whenever the wording changes: it is stored with
every analysis, so results can be traced to the prompt that produced them."""

from app.services.ai.base import ArticleText

PROMPT_VERSION = "2026-11-19.1"

SYSTEM_PROMPT = """You analyze a news article for a busy reader tracking a topic.

You may only see the headline, a short description and the first lines of the article.
Use only that text; never add facts from elsewhere.

Return:
- tldr: one plain sentence (max 30 words) saying what happened.
- key_points: up to 3 short, distinct points (each max 15 words).
- sentiment: the tone of the coverage toward its main subject: positive, neutral or negative.
- score: a number from -1 (very negative) to 1 (very positive); 0 is neutral. It must agree
  with sentiment.
- rationale: one sentence explaining the sentiment.
- evidence: up to 2 short quotes (max 25 words each) copied exactly from the text that
  support the sentiment. Leave it empty if nothing fits."""


def build_input(article: ArticleText) -> str:
    lines = [f"Source: {article.source_name}", f"Headline: {article.title}"]
    if article.description:
        lines.append(f"Description: {article.description}")
    if article.snippet:
        lines.append(f"Opening text: {article.snippet}")
    return "\n".join(lines)
