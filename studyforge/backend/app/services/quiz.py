"""
Quiz generation: produces a validated multiple-choice question grounded in
a specific chunk of the student's own material.

Fallback strategy: if the LLM is unavailable or returns malformed JSON
after retries, we deterministically build a "fill in the blank" style
question by masking a salient noun-like token from a sentence in the
chunk. It's less pedagogically rich than an LLM-authored question, but
it is real, grounded, and never a stub.
"""
from __future__ import annotations

import json
import logging
import random
import re

from app.models.models import Chunk
from app.services.llm import (
    LLMClient,
    QUIZ_SYSTEM_PROMPT,
    build_quiz_user_message,
    parse_quiz_json,
)

logger = logging.getLogger(__name__)

_PARSE_RETRY_ATTEMPTS = 2


class GeneratedQuestion:
    def __init__(self, question_text: str, options: list[str], correct_index: int, explanation: str, method: str):
        self.question_text = question_text
        self.options = options
        self.correct_index = correct_index
        self.explanation = explanation
        self.method = method

    def options_json(self) -> str:
        return json.dumps(self.options)


def generate_question(chunk: Chunk, difficulty: str, llm_client: LLMClient) -> GeneratedQuestion:
    if llm_client.is_configured:
        for attempt in range(1, _PARSE_RETRY_ATTEMPTS + 1):
            result = llm_client.complete(
                system=QUIZ_SYSTEM_PROMPT,
                user_message=build_quiz_user_message(chunk.text, difficulty),
            )
            if result.used_fallback:
                break  # API itself failed after its own retries; go straight to extractive fallback.

            parsed = parse_quiz_json(result.text)
            if parsed is not None:
                return GeneratedQuestion(
                    question_text=parsed["question"],
                    options=parsed["options"],
                    correct_index=parsed["correct_index"],
                    explanation=parsed["explanation"],
                    method="llm",
                )
            logger.warning("Quiz JSON validation failed on attempt %s; retrying.", attempt)

    return _extractive_fallback_question(chunk)


def _extractive_fallback_question(chunk: Chunk) -> GeneratedQuestion:
    """
    Builds a deterministic fill-in-the-blank question: picks the longest
    sentence in the chunk, masks its longest word, and offers the masked
    word plus three random distractor words drawn from the same chunk.
    """
    sentences = re.split(r"(?<=[.!?])\s+", chunk.text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 25] or [chunk.text]
    sentence = max(sentences, key=len)

    words = [w for w in re.findall(r"[A-Za-z]{5,}", sentence)]
    if not words:
        words = [w for w in re.findall(r"[A-Za-z]{3,}", sentence)] or ["concept"]
    answer_word = max(words, key=len)

    all_words = list(set(re.findall(r"[A-Za-z]{5,}", chunk.text)) - {answer_word})
    random.shuffle(all_words)
    distractors = (all_words[:3] + ["context", "process", "structure"])[:3]

    options = [answer_word] + distractors
    random.shuffle(options)
    correct_index = options.index(answer_word)

    masked_sentence = re.sub(rf"\b{re.escape(answer_word)}\b", "ـ____ـ", sentence, count=1)

    return GeneratedQuestion(
        question_text=f"Fill in the blank: {masked_sentence}",
        options=options,
        correct_index=correct_index,
        explanation=f"The original sentence from your material reads: \"{sentence}\"",
        method="extractive_fallback",
    )
