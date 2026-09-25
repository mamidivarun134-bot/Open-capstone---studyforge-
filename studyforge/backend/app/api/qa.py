from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.models.database import get_db
from app.models.models import User
from app.schemas.schemas import AskRequest, AskResponse
from app.services.llm import LLMClient
from app.services.retrieval import answer_question

router = APIRouter(prefix="/api/qa", tags=["qa"])
_llm_client = LLMClient()


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AskResponse:
    return answer_question(
        db=db,
        user_id=current_user.id,
        question=payload.question,
        document_id=payload.document_id,
        llm_client=_llm_client,
    )
