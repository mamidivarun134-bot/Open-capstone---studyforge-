from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.tutor_agent import TutorAgent
from app.api.deps import get_current_user
from app.models.database import get_db
from app.models.models import QuizAttempt, QuizQuestion, User
from app.schemas.schemas import QuizAnswerRequest, QuizAnswerResponse, QuizQuestionOut
from app.services.llm import LLMClient
from app.services.quiz import generate_question

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quiz", tags=["quiz"])
_llm_client = LLMClient()


@router.post("/next", response_model=QuizQuestionOut)
def next_question(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> QuizQuestionOut:
    agent = TutorAgent(db, current_user.id)
    decision = agent.plan_next_topic()
    if decision is None:
        raise HTTPException(
            status_code=400,
            detail="No topics available yet. Upload a document first so StudyForge can build your topic list.",
        )

    chunk = agent.pick_chunk_for_topic(decision.topic.id)
    if chunk is None:
        raise HTTPException(status_code=400, detail="This topic has no source material to generate a question from.")

    generated = generate_question(chunk, decision.difficulty, _llm_client)

    question = QuizQuestion(
        topic_id=decision.topic.id,
        source_chunk_id=chunk.id,
        question_text=generated.question_text,
        options_json=generated.options_json(),
        correct_option_index=generated.correct_index,
        explanation=generated.explanation,
        difficulty=decision.difficulty,
        generation_method=generated.method,
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    logger.info(
        "Agent plan for user=%s: topic='%s' difficulty=%s (%s)",
        current_user.id,
        decision.topic.name,
        decision.difficulty,
        decision.reason,
    )

    return QuizQuestionOut(
        id=question.id,
        topic_name=decision.topic.name,
        question_text=question.question_text,
        options=json.loads(question.options_json),
        difficulty=question.difficulty,
        generation_method=question.generation_method,
    )


@router.post("/answer", response_model=QuizAnswerResponse)
def answer_question_route(
    payload: QuizAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuizAnswerResponse:
    question = db.query(QuizQuestion).filter(QuizQuestion.id == payload.question_id).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")

    is_correct = payload.selected_option_index == question.correct_option_index

    attempt = QuizAttempt(
        user_id=current_user.id,
        question_id=question.id,
        selected_option_index=payload.selected_option_index,
        is_correct=is_correct,
    )
    db.add(attempt)
    db.commit()

    agent = TutorAgent(db, current_user.id)
    updated_mastery = agent.record_attempt_and_update_mastery(question.topic_id, is_correct)
    next_topic = agent.recommend_next_topic_name()

    return QuizAnswerResponse(
        is_correct=is_correct,
        correct_option_index=question.correct_option_index,
        explanation=question.explanation,
        updated_mastery=round(updated_mastery, 4),
        next_recommended_topic=next_topic,
    )
