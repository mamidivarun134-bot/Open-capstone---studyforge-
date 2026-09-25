"""
Chunking: splits page-level text into overlapping windows suitable for
embedding and retrieval.

WHY overlap: without it, a fact split across a chunk boundary becomes
unretrievable because neither half contains the full context. A ~150
character overlap on ~800 character chunks keeps most sentences intact
in at least one chunk.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class PageText:
    page_number: int
    text: str
    source_method: str  # "text" or "ocr"


@dataclass
class TextChunk:
    text: str
    page_number: int | None
    source_method: str


def _clean(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_pages(pages: list[PageText], chunk_size: int = 800, overlap: int = 150) -> list[TextChunk]:
    """
    Chunk each page independently (so page/citation metadata stays accurate),
    using a sliding window over cleaned text.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[TextChunk] = []
    for page in pages:
        cleaned = _clean(page.text)
        if not cleaned:
            continue

        start = 0
        n = len(cleaned)
        while start < n:
            end = min(start + chunk_size, n)
            piece = cleaned[start:end].strip()
            if piece:
                chunks.append(TextChunk(text=piece, page_number=page.page_number, source_method=page.source_method))
            if end == n:
                break
            start = end - overlap
    return chunks
