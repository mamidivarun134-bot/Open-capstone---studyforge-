# StudyForge

An adaptive AI tutor that answers questions and generates quizzes **grounded entirely in your own uploaded course materials**, and tracks per-topic mastery to tell you exactly what to study next.

## Problem

Generic AI chatbots answer study questions from general internet knowledge, which can contradict a specific course's terminology, scope, or emphasis — and they have no memory of which topics you're actually weak on. Students end up either re-reading everything or nothing in particular.

## Solution

Upload your lecture slides, notes, or textbook chapters as a PDF. StudyForge extracts the text (OCR-ing image-heavy pages automatically), indexes it, and automatically groups it into topics. You can then ask questions — every answer cites the exact excerpt it came from — and take an adaptive quiz that an agent builds specifically around your weakest, most-overdue topics, adjusting difficulty as you go.

## Features

- **RAG-grounded Q&A** with mandatory source citations and honest "no match found" responses (no fabricated answers).
- **Automatic OCR fallback** for scanned or image-heavy PDF pages.
- **Unsupervised topic clustering** (KMeans over TF-IDF) — no manual tagging required.
- **Adaptive Tutor Agent**: an explicit Plan → Generate → Evaluate → Update → Replan state machine that picks the next topic and difficulty based on a persisted, recency-aware mastery score.
- **Structured, validated quiz generation** via LLM with a deterministic offline fallback — the app works even with no API key configured.
- **Per-topic mastery dashboard** with a live chart.
- **JWT auth**, so materials and progress are private per user.
- Runs entirely offline in "extractive fallback" mode, or with an Anthropic API key for full LLM-generated answers and questions.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for full Mermaid diagrams (system architecture, agent state machine, RAG pipeline, ER diagram, deployment topology).

```
User → Frontend (vanilla JS) → FastAPI backend
                                   ├── Auth (JWT + bcrypt)
                                   ├── RAG (TF-IDF retrieval + chunking)
                                   ├── Tutor Agent (adaptive quiz loop)
                                   ├── LLM Client (Anthropic API, retries + fallback)
                                   └── SQLite/PostgreSQL + per-user vector store
```

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 |
| Database | SQLite (default) / PostgreSQL (swap via `DATABASE_URL`) |
| RAG / Vector store | scikit-learn TF-IDF + cosine similarity (fully local, no API key needed) |
| Topic modeling | scikit-learn KMeans |
| LLM | Anthropic API (model-abstracted; extractive fallback when unconfigured) |
| Auth | JWT (python-jose) + bcrypt |
| Frontend | Vanilla HTML/CSS/JS (no build step) |
| Testing | pytest + FastAPI TestClient |
| Containerization | Docker + docker-compose |

Full rationale for each choice (including alternatives considered) is in [`docs/REPORT.md`](docs/REPORT.md#technology-stack).

## Screenshots

The frontend is a single-page app with four views: **Library** (upload/manage documents), **Ask** (cited Q&A), **Quiz** (adaptive multiple-choice), and **Progress** (mastery dashboard with a bar chart). Run the app locally (see Installation below) to see it live — screenshots aren't checked into this repository to keep it lightweight.

## Demo

See [`docs/PRESENTATION.md`](docs/PRESENTATION.md) for a full 3-minute demo script walking through upload → ask → adaptive quiz → progress dashboard.

## Installation

### Option A — Docker (recommended)

```bash
git clone <this-repo-url> studyforge
cd studyforge
cp .env.example .env
# Generate a real secret key:
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste the output into SECRET_KEY= in .env

docker compose up --build
```

The app will be available at **http://localhost:8000**.

### Option B — Local (no Docker)

Requires Python 3.12+.

```bash
git clone <this-repo-url> studyforge
cd studyforge

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste the output into SECRET_KEY= in .env

cd backend
uvicorn app.main:app --reload
```

The app will be available at **http://127.0.0.1:8000**.

> **Optional OCR support:** to enable the OCR fallback for scanned/image-heavy PDFs, install `tesseract-ocr` and `poppler-utils` on your system (`apt install tesseract-ocr poppler-utils` on Debian/Ubuntu; the Docker image already includes these). Without them, ingestion still works for any page with a native text layer — OCR is skipped gracefully with a logged warning.

## Environment Variables

See [`.env.example`](.env.example) for the full list with defaults. Key ones:

| Variable | Required? | Purpose |
|---|---|---|
| `SECRET_KEY` | Yes (production) | Signs JWTs. Generate with `secrets.token_urlsafe(32)`. |
| `DATABASE_URL` | No | Defaults to a local SQLite file. Point at a PostgreSQL URL for production. |
| `ANTHROPIC_API_KEY` | No | If unset, the app runs fully offline using extractive fallback logic for both Q&A and quiz generation. |

**Never commit `.env`.** It's already git-ignored.

## Usage

1. Register/sign in.
2. Go to **Library**, drag in a PDF of course material (up to 25 MB).
3. Wait for it to move from "processing" to "ready" — this happens synchronously and typically takes a few seconds for a normal document.
4. Go to **Ask** and ask a question — check the citations.
5. Go to **Quiz**, click "Get a question," answer it, and watch the recommended next topic/difficulty adapt.
6. Check **Progress** for your per-topic mastery chart.

## API Documentation

Interactive OpenAPI docs are auto-generated by FastAPI at **`/docs`** once the server is running (e.g. `http://127.0.0.1:8000/docs`).

Key endpoints:

```
POST /api/auth/register        Create an account
POST /api/auth/login           Get a JWT (OAuth2 password flow)
POST /api/documents/upload     Upload and process a PDF
GET  /api/documents            List your documents
POST /api/qa/ask               Ask a grounded question
POST /api/quiz/next            Get the agent's next adaptive question
POST /api/quiz/answer          Submit an answer, update mastery
GET  /api/dashboard/mastery    Per-topic mastery for the dashboard
GET  /api/health               Health check
```

## AI Architecture

The LLM layer (`backend/app/services/llm.py`) wraps the Anthropic API with a model abstraction, prompt templates, retry-with-backoff, timeout handling, and structured JSON-output validation. When no API key is configured — or the API call keeps failing after retries — the system falls back to deterministic logic (returning the most relevant excerpt for Q&A; generating a fill-in-the-blank question for quizzes) rather than erroring out. See `docs/ARCHITECTURE.md` for details.

## RAG Pipeline

Ingestion → per-page text extraction (with OCR fallback) → sliding-window chunking → per-user TF-IDF indexing → KMeans topic clustering → cosine-similarity retrieval → cited, grounded LLM generation (or extractive fallback). Full pipeline diagram and hallucination-mitigation strategy: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#4-rag-pipeline).

## Agent Architecture

The Tutor Agent (`backend/app/agents/tutor_agent.py`) is an explicit state machine — Plan → Generate → Evaluate → Update → Replan — that makes real decisions (which topic, what difficulty) based on persisted mastery history, not a fixed script. State diagram: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#3-agent-workflow-tutor-agent-state-machine).

## Evaluation

26 automated tests, a documented metrics framework (retrieval precision, groundedness, quiz validity, mastery-tracking sanity, latency, agent task completion rate), and manual spot-checks. Full writeup: [`docs/EVALUATION.md`](docs/EVALUATION.md).

## Testing

```bash
cd backend
source ../.venv/bin/activate   # if not already active
pytest -v
```

All tests run against a fully isolated temp SQLite database and vector store, and force the extractive-fallback path (no real network/LLM calls), so they're deterministic and safe to run without any API key.

## Security

See [`docs/SECURITY.md`](docs/SECURITY.md) for the full review: what's implemented (bcrypt password hashing, JWT auth with per-user data scoping, Pydantic input validation, upload restrictions, parameterized ORM queries, XSS-safe frontend rendering) and what's explicitly out of scope for this version (rate limiting enforcement, email verification, malware scanning on uploads).

## Limitations

- Retrieval is lexical (TF-IDF), not semantic — a heavily paraphrased question may not retrieve the relevant chunk even if the answer is present.
- Document processing runs synchronously on upload; very large PDFs will delay the upload response.
- No production-grade rate limiting, email verification, or "delete my data" flow yet.
- Full details, including bias and hallucination risk discussion: [`docs/RESPONSIBLE_AI.md`](docs/RESPONSIBLE_AI.md).

## Future Improvements

- Swap TF-IDF for semantic embeddings (sentence-transformers or a hosted embeddings API) behind the existing `UserVectorStore` interface.
- Move document processing to a background task queue.
- Introduce LangGraph if the agent's branching logic grows beyond the current linear loop.
- Spaced-repetition scheduling and a personalized study-plan export.

## Contributing

This is a capstone project, but issues and pull requests are welcome. Please run `pytest -v` before submitting a PR and update the relevant `docs/` file if you change architecture, security posture, or responsible-AI considerations.

## License

MIT — see [`LICENSE`](LICENSE).
