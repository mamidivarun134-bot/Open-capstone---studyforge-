# StudyForge — Final Presentation

## Slide-by-slide outline

1. **Problem** — Students use generic AI chat to study, which isn't grounded in what they were actually taught, and have no systematic way to know what they're weak on.
2. **Why this problem matters** — Poor retrieval practice and misallocated study time are well-documented drivers of weak exam performance; human tutoring solves both but doesn't scale.
3. **Existing limitations** — Generic chatbots aren't grounded in course-specific material; static flashcard apps require manual authoring; EdTech tutors use vendor curricula, not the student's own notes.
4. **Proposed solution** — StudyForge: upload your material, ask grounded questions with citations, get an adaptive quiz that targets your actual weak topics.
5. **Architecture** — High-level diagram (frontend → API → RAG/Agent/LLM → DB/vector store); highlight the offline-fallback path.
6. **AI components** — TF-IDF retrieval, KMeans topic clustering, LLM-based structured quiz generation with a validated JSON schema and retries.
7. **Agent workflow** — Plan → Generate → Evaluate → Update → Replan state machine, driven by persisted EMA mastery scores.
8. **RAG pipeline** — Ingestion → OCR fallback → chunking → retrieval → cited generation → honest "no match" handling.
9. **Demo** — (see script below).
10. **Evaluation** — 26 automated tests passing; manual spot-checks of retrieval relevance and groundedness; baseline-vs-improved comparison.
11. **Results** — End-to-end flow verified against a live HTTP server, not just an in-process test client.
12. **Limitations** — Lexical (not semantic) retrieval; synchronous document processing; no production rate limiting yet.
13. **Future work** — Semantic embeddings, background task queue, LangGraph if agent logic grows, spaced repetition.
14. **Conclusion** — A complete, tested, honestly-scoped AI capstone that works with or without a paid API key.

## 3-minute demo script

**[0:00–0:20] Hook**
"Generic AI chatbots will happily answer your exam-prep questions — using knowledge from the entire internet, not from what your professor actually taught. StudyForge fixes that."

**[0:20–0:50] Upload**
- Sign in, go to Library, drag in a PDF of course notes.
- "StudyForge extracts the text — falling back to OCR automatically if a page is image-only — chunks it, and automatically groups it into topics using unsupervised clustering. No manual tagging."
- Point out the document card flipping from "processing" to "ready."

**[0:50–1:30] Ask**
- Go to Ask, type a question that's directly answerable from the uploaded material.
- "The answer comes back with citations pointing to the exact excerpt it used — you can verify it yourself."
- Ask a second, deliberately unrelated question.
- "And when nothing in your material is relevant, it says so — it doesn't make something up."

**[1:30–2:30] Quiz**
- Go to Quiz, click "Get a question."
- "StudyForge picked this topic specifically because it's the one I've studied least or am weakest in — that's the agent making a real decision, not just cycling through questions in document order."
- Answer once correctly, once incorrectly (open a second question).
- "Watch the difficulty and topic selection adapt in response."

**[2:30–2:50] Progress**
- Go to Progress, show the mastery bar chart.
- "Every attempt updates a per-topic mastery score, and this dashboard shows exactly where to focus next."

**[2:50–3:00] Close**
"It's a fully tested, full-stack application — 26 automated tests, a real RAG pipeline with a documented hallucination-mitigation strategy, and it keeps working even without a paid LLM key, just in a lower-fidelity offline mode. That's StudyForge."
