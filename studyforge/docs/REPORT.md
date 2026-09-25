# StudyForge — Capstone Project Report

## Abstract
StudyForge is an adaptive AI tutor that answers questions and generates quizzes grounded exclusively in a student's own uploaded course materials, and tracks per-topic mastery to decide what to study next and at what difficulty. It combines a retrieval-augmented generation (RAG) pipeline, an unsupervised topic-clustering step, and an explicit agentic state machine for adaptive tutoring, with a fully offline fallback path so the system remains useful without a paid LLM API key.

## Introduction
Generic AI chatbots answer from general internet knowledge, which can contradict a specific course's terminology, scope, or emphasis. Meanwhile, students have no systematic way to identify which topics they are actually weak on without external assessment. StudyForge addresses both gaps in a single, cohesive tool.

## Problem Statement
Students studying from lecture slides, textbooks, and notes lack a tool that (a) answers questions strictly grounded in what they were actually taught, with verifiable citations, and (b) adaptively tracks and targets their real per-topic weaknesses rather than serving practice material in document order.

## Objectives
1. Build a complete RAG pipeline over user-uploaded PDF materials, including OCR fallback for image-heavy pages.
2. Build a genuine agentic tutoring loop that plans, generates, evaluates, and adapts — not a decorative LLM wrapper.
3. Provide a usable, professional full-stack product (auth, dashboard, live quiz loop) rather than a notebook demo.
4. Operate correctly, if in a degraded mode, without any paid API key.

## Existing Solutions and Their Limitations
- **Generic LLM chat (ChatGPT, etc.):** not grounded in the student's specific material; no persistent per-topic mastery tracking.
- **Khanmigo and similar EdTech tutors:** grounded in vendor-curated curricula, not the student's own uploaded documents.
- **Static flashcard apps (Anki):** require the student to manually author every card; no automatic grounding, retrieval, or generation.

## Proposed Solution
A FastAPI backend ingests uploaded PDFs, extracts and OCRs text as needed, chunks it, indexes it in a per-user TF-IDF vector store, and clusters chunks into auto-named topics via KMeans. A Q&A endpoint retrieves relevant chunks and synthesizes a cited answer via an LLM (with an extractive fallback). A Tutor Agent — an explicit Plan → Generate → Evaluate → Update → Replan state machine — selects the next topic and difficulty based on a persisted, EMA-based mastery score per topic, generates a grounded multiple-choice question (LLM-authored, with a deterministic fallback), and updates mastery after each answer. A vanilla-JS single-page frontend provides upload, Q&A, quiz, and a mastery dashboard.

## System Architecture
See `docs/ARCHITECTURE.md` for full Mermaid diagrams covering the high-level architecture, the agent state machine, the RAG pipeline, the entity-relationship model, and deployment topology.

## Methodology
Development proceeded through explicit phases: problem discovery and comparison of five candidate capstone ideas, project specification (MVP vs. stretch features, success metrics, non-goals), architecture design, incremental implementation with tests written alongside each service, and a live end-to-end smoke test against the running HTTP server (not just in-process test client) before packaging.

## Technology Stack

| Layer | Choice | Why | Alternative considered |
|---|---|---|---|
| Backend framework | FastAPI | Async, automatic OpenAPI docs, strong Pydantic integration | Flask (less built-in validation/async support) |
| Database ORM | SQLAlchemy 2.0 | Dialect-agnostic; SQLite for zero-config dev, trivially swappable to Postgres | Raw SQL (more error-prone, no migration path) |
| Vector store | Custom TF-IDF + cosine similarity (scikit-learn) | Zero-cost, zero external dependency, works fully offline | Sentence-transformers (requires large model download) or hosted embeddings API (requires paid key) — documented as a future swap |
| Topic modeling | KMeans (scikit-learn) | Simple, deterministic, works directly on existing TF-IDF vectors with no extra dependency | LDA (more complex, less predictable for small per-user corpora) |
| LLM | Anthropic API (Claude), model-abstracted | High-quality structured output, generous JSON-following behavior | OpenAI API (equally viable; abstraction layer would need a small adapter change) |
| Agent architecture | Hand-rolled explicit state machine | Fully sufficient for a linear plan → act → evaluate → update loop; avoids an unnecessary heavyweight dependency | LangGraph — documented as the natural upgrade path if the decision logic grows more branches |
| Auth | JWT (python-jose) + bcrypt | Stateless, standard, well-understood security properties | Session cookies (more server state, unnecessary here) |
| Frontend | Vanilla HTML/CSS/JS | Zero build step — the zipped project runs immediately | React/Vite (adds a build step with no proportional benefit at this scope) |
| Containerization | Docker + docker-compose | One-command reproducible deployment | Bare-metal install only (still supported as the non-Docker path) |

## Implementation
See the `backend/app/` package: `core/` (config, security, logging), `models/` (SQLAlchemy schema), `schemas/` (Pydantic I/O contracts), `services/` (ingestion, LLM client, retrieval, quiz generation, document pipeline), `agents/` (the Tutor Agent), `rag/` (chunking, vector store), and `api/` (route handlers). Every function that touches an external boundary (LLM API, file I/O, database) includes explicit error handling and logging.

## AI Architecture
The LLM layer (`app/services/llm.py`) provides model abstraction, prompt templates, retry-with-backoff, timeout handling, and structured-output validation (`parse_quiz_json`). When unconfigured or persistently failing, callers fall back to deterministic logic rather than erroring — this fallback is itself real, tested code (`_extractive_fallback_question`, the extractive branch of `answer_question`), not a stub.

## RAG Architecture
See `docs/ARCHITECTURE.md` §4 for the full pipeline diagram and the hallucination-reduction strategy (excerpt-only grounding, mandatory citations, honest "no match" responses, and a non-fabricating fallback).

## Agent Architecture
See `docs/ARCHITECTURE.md` §3 for the state diagram. The agent's decisions (`TutorAgent.plan_next_topic`) are driven by persisted state (per-topic EMA mastery + recency), not hardcoded — verified by `tests/test_agent.py`, which asserts that difficulty rises with mastery and falls with repeated incorrect answers.

## Database Design
See `docs/ARCHITECTURE.md` §5 for the entity-relationship diagram covering seven entities (User, Document, Chunk, Topic, QuizQuestion, QuizAttempt, MasteryRecord) and their relationships.

## Testing
26 automated tests across unit (auth, RAG, quiz, agent) and integration (full API flow against a real generated PDF) levels; see `docs/EVALUATION.md` for the breakdown and `backend/tests/`. A live HTTP smoke test (real `uvicorn` process, real `curl` requests, not just `TestClient`) was additionally run and its output is embedded in `docs/EVALUATION.md`.

## Evaluation
See `docs/EVALUATION.md` for the full metrics framework, automated test results, manual spot-checks, and a baseline-vs-improved comparison table.

## Results
The system correctly: extracts and chunks PDF text; falls back to OCR only where needed; retrieves relevant material via TF-IDF cosine similarity; clusters chunks into sensible topics via KMeans; answers grounded questions with citations (or honestly reports no match); generates valid, schema-checked quiz questions (LLM path) or a deterministic fallback question (offline path); updates per-topic mastery correctly in the direction expected of correct/incorrect answers; and increases/decreases served difficulty accordingly.

## Security
See `docs/SECURITY.md` for the full review, including what's implemented (bcrypt hashing, JWT auth with per-user data scoping, Pydantic validation, upload restrictions, parameterized ORM queries, XSS-safe frontend rendering, generic error responses) and what's explicitly out of scope for this version (rate limiting enforcement, email verification, malware scanning).

## Responsible AI
See `docs/RESPONSIBLE_AI.md` for a full accounting of limitations (lexical-only retrieval, ungrounded-material-in-ungrounded-material-out, heuristic mastery scoring), possible biases (topic clustering unevenness, document-length coverage skew), hallucination risks, privacy considerations, and appropriate/inappropriate usage guidance.

## Limitations
- Retrieval is lexical (TF-IDF), not semantic — documented as the clearest near-term upgrade path.
- Document processing runs synchronously on upload; large documents will block the request until processing completes.
- No production-grade rate limiting, email verification, or data-deletion flow yet.

## Future Scope
- Swap TF-IDF for semantic embeddings (sentence-transformers or a hosted embeddings API) behind the existing `UserVectorStore` interface.
- Move document processing to a background task queue.
- Introduce LangGraph if the agent's branching logic grows (e.g. multi-step remediation plans, teacher-facing classroom analytics).
- Add spaced-repetition scheduling and a "study plan" export.

## Conclusion
StudyForge demonstrates a complete, tested, honestly-scoped AI engineering capstone: a real RAG pipeline with a documented hallucination-mitigation strategy, a genuine agentic tutoring loop with persisted decision state, graceful degradation when no paid API is configured, and a full-stack product a student could actually use — built and verified end-to-end rather than described in the abstract.

## References
- Robertson, S. (2004). Understanding inverse document frequency: on theoretical arguments for IDF. *Journal of Documentation.*
- Lloyd, S. (1982). Least squares quantization in PCM. *IEEE Transactions on Information Theory* (the K-means algorithm).
- Lewis, P. et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS.*
- FastAPI documentation: https://fastapi.tiangolo.com
- SQLAlchemy documentation: https://docs.sqlalchemy.org
- Anthropic API documentation: https://docs.claude.com
