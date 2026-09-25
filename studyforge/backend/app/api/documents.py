from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.models.database import get_db
from app.models.models import Document, User
from app.schemas.schemas import DocumentOut
from app.services.document_pipeline import process_document

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/documents", tags=["documents"])

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
_ALLOWED_CONTENT_TYPES = {"application/pdf"}


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentOut:
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 25 MB).")
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    os.makedirs(settings.RAW_DATA_DIR, exist_ok=True)
    safe_name = f"{current_user.id}_{uuid.uuid4().hex}.pdf"
    storage_path = os.path.join(settings.RAW_DATA_DIR, safe_name)
    with open(storage_path, "wb") as f:
        f.write(contents)

    document = Document(
        owner_id=current_user.id,
        filename=file.filename or "untitled.pdf",
        storage_path=storage_path,
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Synchronous processing keeps this project's demo simple (no task queue
    # dependency). For production scale this would be handed to a background
    # worker (see docs/ARCHITECTURE.md, "Future Improvements").
    process_document(db, document)
    db.refresh(document)

    return DocumentOut.model_validate(document)


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[DocumentOut]:
    docs = db.query(Document).filter(Document.owner_id == current_user.id).order_by(Document.created_at.desc()).all()
    return [DocumentOut.model_validate(d) for d in docs]
