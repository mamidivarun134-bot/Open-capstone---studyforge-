# StudyForge — System Architecture

## 1. High-level architecture

```mermaid
flowchart TB
    User([Student])
    FE["Frontend<br/>(vanilla HTML/CSS/JS, served by FastAPI)"]
    API["Backend API<br/>(FastAPI)"]
    AUTH["Auth<br/>(JWT + bcrypt)"]
    ORCH["AI Orchestration Layer"]
    LLM["LLM Client<br/>(Anthropic API, retry/timeout/fallback)"]
    RAG["RAG Pipeline<br/>(chunking + TF-IDF retrieval)"]
    AGENT["Tutor Agent<br/>(Plan / Generate / Evaluate / Update / Replan)"]
    QUIZ["Quiz Service<br/>(structured generation + extractive fallback)"]
    DB[("SQLite / PostgreSQL<br/>users, documents, chunks, topics, attempts")]
    VS[("Per-user TF-IDF vector store<br/>(joblib, on disk)")]
    FILES[("Raw PDF storage<br/>data/raw/")]

    User --> FE --> API
    API --> AUTH
    API --> ORCH
    ORCH --> LLM
    ORCH --> RAG
    ORCH --> AGENT
    ORCH --> QUIZ
    RAG --> VS
    RAG --> DB
    AGENT --> DB
    QUIZ --> LLM
    QUIZ --> DB
    API --> FILES
    API --> DB
```

## 2. Why each component exists

| Component | Why it's needed |
|---|---|
| **FastAPI backend** | Async-friendly, automatic OpenAPI docs, first-class Pydantic validation — the standard choice for a Python AI backend. |
| **JWT auth** | Keeps the API stateless (no server-side session store needed at this scale) while keeping each student's materials and progress private. |
| **SQLAlchemy + SQLite (default) / PostgreSQL (production)** | SQLite needs zero setup for local dev and grading; swapping `DATABASE_URL` to a Postgres URL is the only change needed for production, since SQLAlchemy abstracts the dialect. |
| **TF-IDF vector store (per user)** | Fully local, zero-cost, zero-API-key embedding + retrieval. Swappable: `UserVectorStore.rebuild`/`search` are the only two methods that would change to plug in sentence-transformers or a hosted embeddings API. |
| **LLM Client (Anthropic API)** | Generates grounded answers and quiz questions with retries, timeouts, and structured-output validation — never a bare unvalidated prompt-to-text call. |
| **Extractive fallback** | If no `ANTHROPIC_API_KEY` is set (or the API is down), the system still functions: it returns the most relevant excerpt for Q&A and a deterministic fill-in-the-blank question for quizzes, instead of failing. |
| **Tutor Agent** | The agentic core: decides *which* topic and *what difficulty* to serve next based on persisted mastery history — a real decision, not a fixed script. |
| **KMeans topic clustering** | The ML component: automatically groups a newly uploaded document's chunks into topics without requiring the student to manually tag anything. |
| **Frontend (vanilla JS)** | No build step, so the zipped project runs by simply starting the backend — the backend serves the frontend as static files. |

## 3. Agent workflow (Tutor Agent state machine)

```mermaid
stateDiagram-v2
    [*] --> Plan
    Plan: PLAN\nSelect weakest/most-overdue topic\n+ appropriate difficulty
    Plan --> Generate
    Generate: GENERATE\nPick a source chunk for that topic\n→ LLM or extractive question generation
    Generate --> AwaitAnswer
    AwaitAnswer: (student answers via UI)
    AwaitAnswer --> Evaluate
    Evaluate: EVALUATE\nCompare selected option to correct_option_index
    Evaluate --> Update
    Update: UPDATE\nEMA mastery update per topic\n+ record attempt history
    Update --> Replan
    Replan: REPLAN\nRecompute next recommended topic
    Replan --> Plan: student requests next question
    Replan --> [*]: student ends session
```

## 4. RAG pipeline

```mermaid
flowchart LR
    A[Upload PDF] --> B["Extract text per page<br/>(pypdf)"]
    B -->|"low/no text"| C["OCR fallback<br/>(pytesseract + pdf2image)"]
    B -->|"text present"| D[Chunk pages]
    C --> D
    D --> E["Persist Chunk rows<br/>(text, page, source_method)"]
    E --> F["Rebuild TF-IDF vectorizer<br/>over full user corpus"]
    F --> G["KMeans clustering<br/>→ auto-named Topics"]
    G --> H[Ready for retrieval & quizzing]

    Q[Student question] --> I["TF-IDF query vector<br/>+ cosine similarity"]
    I --> J["Top-k chunks retrieved"]
    J --> K["LLM synthesis<br/>(grounded, cited)"]
    J -->|"no LLM key"| L["Extractive fallback<br/>(best chunk verbatim)"]
```

**Hallucination-reduction strategy:**
1. The LLM is instructed to answer *only* from the retrieved excerpts.
2. Every excerpt shown to the model is also returned to the student as a citation.
3. If retrieval finds nothing relevant, the system says so rather than letting the model improvise.
4. If the LLM is unavailable, the extractive fallback returns a real excerpt rather than a synthesized (and unverifiable) answer.

## 5. Entity-relationship diagram

```mermaid
erDiagram
    USER ||--o{ DOCUMENT : uploads
    USER ||--o{ TOPIC : owns
    USER ||--o{ MASTERY_RECORD : tracks
    USER ||--o{ QUIZ_ATTEMPT : makes
    DOCUMENT ||--o{ CHUNK : "split into"
    TOPIC ||--o{ CHUNK : groups
    TOPIC ||--o{ QUIZ_QUESTION : "generates from"
    TOPIC ||--o{ MASTERY_RECORD : "measured by"
    QUIZ_QUESTION ||--o{ QUIZ_ATTEMPT : answered_by
    CHUNK ||--o{ QUIZ_QUESTION : "sources"

    USER {
        int id PK
        string email
        string hashed_password
        datetime created_at
    }
    DOCUMENT {
        int id PK
        int owner_id FK
        string filename
        string storage_path
        int page_count
        int ocr_pages
        string status
    }
    TOPIC {
        int id PK
        int owner_id FK
        string name
    }
    CHUNK {
        int id PK
        int document_id FK
        int topic_id FK
        int chunk_index
        int page_number
        text text
        string source_method
        int vector_row
    }
    QUIZ_QUESTION {
        int id PK
        int topic_id FK
        int source_chunk_id FK
        text question_text
        text options_json
        int correct_option_index
        string difficulty
        string generation_method
    }
    QUIZ_ATTEMPT {
        int id PK
        int user_id FK
        int question_id FK
        int selected_option_index
        bool is_correct
    }
    MASTERY_RECORD {
        int id PK
        int user_id FK
        int topic_id FK
        float mastery_score
        int attempts_count
        datetime last_reviewed_at
    }
```

## 6. Deployment topology

```mermaid
flowchart LR
    subgraph Client
        Browser
    end
    subgraph Server["Single container (docker-compose)"]
        FastAPI["FastAPI app<br/>(serves API + static frontend)"]
        SQLite[("SQLite file<br/>./data/processed/")]
        VectorStore[("TF-IDF store<br/>./data/processed/vector_store")]
        RawFiles[("Uploaded PDFs<br/>./data/raw")]
    end
    ExternalLLM[["Anthropic API<br/>(optional, external)"]]

    Browser <--> FastAPI
    FastAPI <--> SQLite
    FastAPI <--> VectorStore
    FastAPI <--> RawFiles
    FastAPI -.->|"if ANTHROPIC_API_KEY set"| ExternalLLM
```

## 7. Future improvements to this architecture

- Move document processing (`process_document`) to a background task queue (e.g. Celery/RQ) instead of running synchronously on the upload request, so large PDFs don't block the HTTP response.
- Swap the TF-IDF vector store for sentence-transformers or a hosted embeddings API for semantic (not just lexical) retrieval — the `UserVectorStore` interface was designed to make this a contained change.
- Introduce LangGraph if the agent's decision logic grows more branches (e.g. multi-step remediation plans) than the current linear state machine comfortably expresses.
- Add multi-tenant classroom analytics (teacher dashboards aggregating multiple students' mastery).
