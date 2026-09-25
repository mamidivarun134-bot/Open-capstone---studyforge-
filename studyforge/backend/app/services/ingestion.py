"""
Document ingestion: extracts text from an uploaded PDF, page by page,
falling back to OCR for pages that contain little/no extractable text
(e.g. slide decks exported as images, scanned notes).

WHY per-page OCR fallback rather than OCR-everything: native text
extraction is faster and more accurate than OCR whenever it's available;
OCR is reserved for pages where it's actually needed. This is the
project's multimodal capability (Phase 11): image-heavy course slides
become searchable text.

OCR is best-effort: if pytesseract/tesseract isn't installed in the
runtime environment, ingestion still succeeds for the text layer and
logs a warning rather than failing the whole upload.
"""
from __future__ import annotations

import logging

from pypdf import PdfReader

from app.rag.chunking import PageText

logger = logging.getLogger(__name__)

_MIN_CHARS_BEFORE_OCR = 20  # below this, treat the page as "no text layer" and try OCR

try:
    import pytesseract
    from pdf2image import convert_from_path

    _OCR_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when optional deps are absent
    _OCR_AVAILABLE = False


class IngestionError(Exception):
    pass


def extract_pages(pdf_path: str) -> list[PageText]:
    """Extracts text per page, using OCR as a fallback for image-only pages."""
    try:
        reader = PdfReader(pdf_path)
    except Exception as exc:  # malformed/corrupt PDF
        raise IngestionError(f"Could not read PDF: {exc}") from exc

    pages: list[PageText] = []
    ocr_images = None

    for i, page in enumerate(reader.pages):
        page_number = i + 1
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # some malformed pages can raise inside pypdf
            logger.warning("Text extraction failed on page %s: %s", page_number, exc)
            text = ""

        if len(text.strip()) >= _MIN_CHARS_BEFORE_OCR:
            pages.append(PageText(page_number=page_number, text=text, source_method="text"))
            continue

        # Fall back to OCR for this page.
        if not _OCR_AVAILABLE:
            logger.warning(
                "Page %s has little/no extractable text and OCR is unavailable "
                "(install tesseract-ocr + poppler-utils to enable it). Skipping page.",
                page_number,
            )
            continue

        try:
            if ocr_images is None:
                ocr_images = convert_from_path(pdf_path)
            image = ocr_images[i]
            ocr_text = pytesseract.image_to_string(image)
        except Exception as exc:
            logger.warning("OCR failed on page %s: %s", page_number, exc)
            continue

        if ocr_text.strip():
            pages.append(PageText(page_number=page_number, text=ocr_text, source_method="ocr"))

    if not pages:
        raise IngestionError("No extractable text found in this document (even after attempting OCR).")

    return pages
