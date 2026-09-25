"""
LLM abstraction layer.

Design goals (Phase 8 requirements):
  - model abstraction: callers depend on `LLMClient`, not on a specific SDK
  - structured outputs: quiz generation requests strict JSON and validates it
  - retries + timeout: transient API failures don't crash a request
  - fallback: if no ANTHROPIC_API_KEY is configured (or the API call keeps
    failing), the system degrades to a deterministic extractive method
    instead of returning an error. This satisfies the "free/local fallback"
    requirement for a paid API without requiring a second heavyweight model.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    import anthropic

    _SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SDK_AVAILABLE = False


@dataclass
class LLMResult:
    text: str
    used_fallback: bool


class LLMClient:
    """Thin wrapper around the Anthropic API with retry/timeout/fallback handling."""

    def __init__(self) -> None:
        self._client = None
        if _SDK_AVAILABLE and settings.ANTHROPIC_API_KEY:
            self._client = anthropic.Anthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                base_url=settings.ANTHROPIC_BASE_URL,
                default_headers={
                    "Authorization": f"Bearer {settings.ANTHROPIC_API_KEY}",
                },
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def complete(self, system: str, user_message: str) -> LLMResult:
        """
        Calls the LLM with retries. Returns used_fallback=True (with an
        empty text) if no client is configured or all retries fail, so
        callers can invoke their own deterministic fallback logic.
        """
        if not self.is_configured:
            logger.info("No ANTHROPIC_API_KEY configured; caller should use fallback logic.")
            return LLMResult(text="", used_fallback=True)

        last_error: Exception | None = None
        for attempt in range(1, settings.LLM_MAX_RETRIES + 2):
            try:
                response = self._client.messages.create(
                    model=settings.LLM_MODEL,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    system=system,
                    messages=[{"role": "user", "content": user_message}],
                )
                text_blocks = [block.text for block in response.content if block.type == "text"]
                return LLMResult(text="\n".join(text_blocks), used_fallback=False)
            except Exception as exc:  # noqa: BLE001 - deliberately broad: any SDK/network failure should retry
                last_error = exc
                wait = min(2 ** attempt, 8)
                logger.warning("LLM call failed (attempt %s): %s. Retrying in %ss.", attempt, exc, wait)
                time.sleep(wait if attempt <= settings.LLM_MAX_RETRIES else 0)

        logger.error("LLM call failed after %s attempts: %s", settings.LLM_MAX_RETRIES + 1, last_error)
        return LLMResult(text="", used_fallback=True)


# --- Prompt templates ---

RAG_ANSWER_SYSTEM_PROMPT = """You are StudyForge, a study assistant. Answer the student's question \
using ONLY the provided source excerpts. If the excerpts don't contain the answer, say so plainly \
instead of guessing. Keep answers concise and reference which excerpt(s) support each claim by their \
bracketed number, e.g. [1]. Do not invent information that isn't in the excerpts."""


def build_rag_user_message(question: str, excerpts: list[str]) -> str:
    numbered = "\n\n".join(f"[{i + 1}] {excerpt}" for i, excerpt in enumerate(excerpts))
    return f"Source excerpts:\n{numbered}\n\nStudent question: {question}"


QUIZ_SYSTEM_PROMPT = """You generate multiple-choice quiz questions strictly grounded in a provided \
source excerpt. Respond with ONLY a JSON object (no markdown fences, no commentary) matching exactly \
this schema:
{"question": string, "options": [string, string, string, string], "correct_index": integer (0-3), \
"explanation": string}
The question and correct answer must be fully supported by the excerpt. Do not use outside knowledge."""


def build_quiz_user_message(excerpt: str, difficulty: str) -> str:
    return f"Difficulty: {difficulty}\n\nSource excerpt:\n{excerpt}"


def parse_quiz_json(raw_text: str) -> dict | None:
    """Extracts and validates the structured quiz JSON from a model response."""
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    required_keys = {"question", "options", "correct_index", "explanation"}
    if not required_keys.issubset(data.keys()):
        return None
    if not isinstance(data["options"], list) or len(data["options"]) != 4:
        return None
    if not isinstance(data["correct_index"], int) or not (0 <= data["correct_index"] <= 3):
        return None
    return data
