"""
RAG orchestration: retrieval -> context construction -> LLM generation
-> citation attachment.

Hallucination-reduction strategy (documented per Phase 9 requirement):
  1. The LLM is instructed to answer ONLY from the provided excerpts.
  2. Every excerpt shown to the model is also returned to the user as a
     citation, so the student can verify the answer against the source.
  3. If retrieval finds nothing relevant (empty result set), we do not
     call the LLM at all -- we tell the student we found nothing, rather
     than letting the model improvise an answer with no grounding.
  4. If the LLM is unavailable, we fall back to returning the single most
     similar excerpt verbatim as an "extractive" answer instead of
     fabricating a synthesized one.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.models import Chunk, Document
from app.rag.vector_store import UserVectorStore
from app.schemas.schemas import AskResponse, SourceCitation
from app.services.llm import LLMClient, RAG_ANSWER_SYSTEM_PROMPT, build_rag_user_message

logger = logging.getLogger(__name__)
settings = get_settings()


def answer_question(
    db: Session,
    user_id: int,
    question: str,
    document_id: int | None,
    llm_client: LLMClient,
) -> AskResponse:
    store = UserVectorStore(settings.VECTOR_STORE_DIR, user_id)
    results = store.search(question, top_k=settings.TOP_K_RETRIEVAL)

    if not results:
        return AskResponse(
            answer="I couldn't find anything in your uploaded materials that relates to this question. "
            "Try rephrasing, or upload a document that covers this topic.",
            citations=[],
            generation_method="no_match",
        )

    # Map vector-store row indices back to Chunk rows, in the same order they were inserted.
    all_chunks: list[Chunk] = (
        db.query(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Document.owner_id == user_id)
        .order_by(Chunk.vector_row.asc())
        .all()
    )
    row_to_chunk = {c.vector_row: c for c in all_chunks}

    matched_chunks: list[tuple[Chunk, float]] = []
    for r in results:
        chunk = row_to_chunk.get(r.row_index)
        if chunk is None:
            continue
        if document_id is not None and chunk.document_id != document_id:
            continue
        matched_chunks.append((chunk, r.similarity))

    if not matched_chunks:
        return AskResponse(
            answer="I couldn't find anything relevant in the selected document for this question.",
            citations=[],
            generation_method="no_match",
        )

    excerpts = [c.text for c, _ in matched_chunks]
    llm_result = llm_client.complete(
        system=RAG_ANSWER_SYSTEM_PROMPT,
        user_message=build_rag_user_message(question, excerpts),
    )

    if llm_result.used_fallback:
        # Extractive fallback: surface the most similar excerpt directly rather than guessing.
        best_chunk, best_sim = matched_chunks[0]
        answer_text = (
            "No LLM is configured, so here is the most relevant excerpt from your materials "
            f"(similarity {best_sim:.2f}):\n\n{best_chunk.text}"
        )
        generation_method = "extractive_fallback"
    else:
        answer_text = llm_result.text
        generation_method = "llm"

    citations = [
        SourceCitation(
            chunk_id=chunk.id,
            document_filename=chunk.document.filename,
            page_number=chunk.page_number,
            excerpt=chunk.text[:280],
            similarity=round(similarity, 4),
        )
        for chunk, similarity in matched_chunks
    ]

    return AskResponse(answer=answer_text, citations=citations, generation_method=generation_method)
