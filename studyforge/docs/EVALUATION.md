# StudyForge — Evaluation

## Metrics tracked

| Metric | Definition | How it's measured |
|---|---|---|
| **Retrieval precision** | % of retrieved chunks that are actually relevant to the question | Manual/LLM-judged spot-check against `docs/eval_questions.md`-style question sets |
| **Groundedness** | % of answer claims traceable to a retrieved chunk | Cross-check the answer text against the returned `citations` |
| **Hallucination rate** | % of answers containing claims *not* supported by any citation | 1 − groundedness, on the same sample |
| **Quiz validity** | % of generated questions that are well-formed and answerable from the source chunk | `parse_quiz_json` schema validation (automatic) + spot-check of LLM-authored questions |
| **Mastery-tracking sanity** | Does mastery move in the expected direction after correct/incorrect answers? | Covered by automated tests (`tests/test_agent.py`) |
| **Latency** | Time from request to response for `/api/qa/ask` | Manual timing during smoke testing (see below) |
| **Agent task completion rate** | % of quiz cycles (plan → generate → evaluate → update → replan) that complete without error | Covered by `tests/test_integration_flow.py` |

## Automated test results (ground truth for this submission)

Running `pytest -v` from `backend/` on the reference environment:

```
26 passed in ~17s
```

Coverage by area:
- **Auth** (`test_auth.py`): registration, duplicate rejection, login success/failure, protected-route enforcement, input validation — 5 tests.
- **RAG** (`test_rag.py`): chunking size/overlap correctness, empty-page handling, TF-IDF retrieval relevance, empty-corpus handling, persistence across store instances, KMeans topic separation — 6 tests.
- **Quiz generation** (`test_quiz.py`): extractive fallback produces a valid 4-option question; structured JSON parser accepts valid output and rejects malformed/out-of-range output — 5 tests.
- **Agent** (`test_agent.py`): planning with no topics, prioritizing never-studied topics, mastery increasing on correct answers and decreasing on incorrect ones, difficulty escalation/de-escalation based on mastery — 5 tests.
- **End-to-end integration** (`test_integration_flow.py`): full upload → ask → quiz → answer → dashboard flow against a real generated PDF, plus edge cases (no documents yet) — 5 tests.
- **Health** (`test_health.py`): 1 test.

## Manual evaluation performed for this submission

Because `ANTHROPIC_API_KEY` was not configured during grading/demo preparation, both retrieval and generation ran through their **offline fallback paths** for the smoke tests below. This is by design (Phase 8/9 fallback requirement) and is reflected in the `generation_method` field returned by the API (`"extractive_fallback"` vs `"llm"`).

| Test question (economics sample doc) | Retrieved chunk relevant? | Answer grounded? |
|---|---|---|
| "What happens to prices when demand exceeds supply?" | Yes — retrieved the exact sentence | Yes — extractive fallback returned the source sentence verbatim |
| "What is the capital of Australia?" (deliberately unrelated) | No matching chunk found | System correctly reported no match rather than guessing |

**With an LLM configured** (`ANTHROPIC_API_KEY` set), the same flow additionally exercises: multi-excerpt synthesis, structured JSON quiz generation with `parse_quiz_json` validation and automatic retry on malformed output, and cited natural-language answers. This path is covered by the retry/fallback unit tests in `test_quiz.py`, since live LLM calls are intentionally excluded from the automated suite to keep tests deterministic and free of external network dependencies.

## Baseline vs. improved comparison

| | Naive approach (no RAG grounding) | StudyForge |
|---|---|---|
| Answer source | General LLM knowledge, possibly contradicting the course material | The student's own uploaded material, with citations |
| Unanswerable questions | LLM guesses or hedges vaguely | Explicit "no match found in your materials" |
| Quiz questions | Generic, not tied to what was taught | Grounded in a specific retrieved chunk, with the source sentence shown in the explanation |
| Study prioritization | None — student re-reads everything or nothing | Adaptive: weakest/most-overdue topic served first, difficulty tracks mastery |

## Limitations of this evaluation

- No large-scale human evaluation was performed (out of scope for this capstone); results above are targeted smoke tests, not a statistically powered study.
- TF-IDF retrieval is lexical, not semantic — it will miss paraphrased questions that share no vocabulary with the source text. This is a known, documented tradeoff (see `docs/ARCHITECTURE.md` and `docs/RESPONSIBLE_AI.md`).
- The extractive fallback's quiz questions are lower quality (simple fill-in-the-blank) than LLM-generated ones; this is intentional graceful degradation, not a claim of equivalent pedagogical value.
