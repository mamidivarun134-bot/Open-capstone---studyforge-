"""
End-to-end document processing pipeline, run synchronously after upload:

    PDF file
      -> extract_pages (text + OCR fallback)
      -> chunk_pages (sliding window)
      -> persist Chunk rows (topic_id null for now)
      -> rebuild the user's TF-IDF vector store over ALL of their chunks
      -> cluster chunks into topics (KMeans over TF-IDF vectors)
      -> auto-name each topic from its top TF-IDF terms
      -> assign topic_id back onto each Chunk

Rebuilding the whole user corpus on every upload (rather than incremental
indexing) is a deliberate simplicity/robustness tradeoff appropriate to
this project's scale -- TF-IDF vocabularies aren't stable across partial
refits, and a full rebuild keeps retrieval and clustering consistent.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.models import Chunk, Document, Topic
from app.rag.chunking import chunk_pages
from app.rag.vector_store import UserVectorStore
from app.services.ingestion import IngestionError, extract_pages

logger = logging.getLogger(__name__)
settings = get_settings()


def process_document(db: Session, document: Document) -> None:
    document.status = "processing"
    db.commit()

    try:
        pages = extract_pages(document.storage_path)
    except IngestionError as exc:
        document.status = "failed"
        document.error_message = str(exc)
        db.commit()
        logger.error("Ingestion failed for document %s: %s", document.id, exc)
        return

    document.page_count = len(pages)
    document.ocr_pages = sum(1 for p in pages if p.source_method == "ocr")

    text_chunks = chunk_pages(pages, chunk_size=settings.CHUNK_SIZE_CHARS, overlap=settings.CHUNK_OVERLAP_CHARS)
    if not text_chunks:
        document.status = "failed"
        document.error_message = "No usable text chunks were produced from this document."
        db.commit()
        return

    # Persist new chunks first (vector_row assigned after we know the full corpus order).
    new_chunk_rows: list[Chunk] = []
    for i, tc in enumerate(text_chunks):
        chunk = Chunk(
            document_id=document.id,
            chunk_index=i,
            page_number=tc.page_number,
            text=tc.text,
            source_method=tc.source_method,
            vector_row=-1,  # placeholder, fixed below
        )
        db.add(chunk)
        new_chunk_rows.append(chunk)
    db.commit()

    # Rebuild the full corpus for this user (existing chunks from other documents + new ones),
    # in a stable order, then assign vector_row = position in that order.
    all_chunks: list[Chunk] = (
        db.query(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Document.owner_id == document.owner_id)
        .order_by(Chunk.id.asc())
        .all()
    )
    corpus_texts = [c.text for c in all_chunks]

    store = UserVectorStore(settings.VECTOR_STORE_DIR, document.owner_id)
    store.rebuild(corpus_texts)
    for row_index, chunk in enumerate(all_chunks):
        chunk.vector_row = row_index
    db.commit()

    _assign_topics(db, document.owner_id, all_chunks, store)

    document.status = "ready"
    db.commit()
    logger.info(
        "Document %s processed: %s pages (%s via OCR), %s total chunks in corpus.",
        document.id,
        document.page_count,
        document.ocr_pages,
        len(all_chunks),
    )


def _assign_topics(db: Session, owner_id: int, all_chunks: list[Chunk], store: UserVectorStore) -> None:
    """Clusters the user's full chunk corpus into topics and (re)assigns topic_id on each chunk."""
    n_clusters = min(settings.DEFAULT_TOPIC_COUNT, len(all_chunks))
    labels = store.cluster_topics(n_clusters=n_clusters)
    if not labels:
        return

    # Remove the user's previous auto-generated topic assignments so relabeling stays consistent
    # (topics themselves are kept if they still have chunks after reassignment; orphans are pruned).
    label_to_rows: dict[int, list[int]] = {}
    for row_index, label in enumerate(labels):
        label_to_rows.setdefault(label, []).append(row_index)

    existing_topics = {t.name: t for t in db.query(Topic).filter(Topic.owner_id == owner_id).all()}

    for label, row_indices in label_to_rows.items():
        top_terms = store.top_terms_for_rows(row_indices, top_n=3)
        topic_name = ", ".join(top_terms).title() if top_terms else f"Topic {label + 1}"

        topic = existing_topics.get(topic_name)
        if topic is None:
            topic = Topic(owner_id=owner_id, name=topic_name)
            db.add(topic)
            db.flush()
            existing_topics[topic_name] = topic

        for row_index in row_indices:
            all_chunks[row_index].topic_id = topic.id

    db.commit()

    # Prune topics that ended up with zero chunks (can happen after re-clustering on new uploads).
    orphaned = (
        db.query(Topic)
        .filter(Topic.owner_id == owner_id)
        .filter(~Topic.chunks.any())
        .all()
    )
    for topic in orphaned:
        db.delete(topic)
    db.commit()
