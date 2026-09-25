"""
TutorAgent: the agentic core of StudyForge.

Architecture (explicit state machine, not a bare LLM call):

    User requests next question
            |
            v
       [ PLAN ]  <-- selects the weakest / most overdue topic + difficulty
            |
            v
     [ GENERATE ]  <-- picks a source chunk for that topic, generates a question
            |
            v
      (question shown to student, student answers)
            |
            v
     [ EVALUATE ]  <-- checks the submitted answer against the correct index
            |
            v
       [ UPDATE ]  <-- updates the student's mastery estimate for that topic
            |
            v
      [ REPLAN ]  <-- recomputes which topic should be served next

Why this is a real agent and not a decorative wrapper: each state has its
own input/output contract, the PLAN/REPLAN steps make an actual decision
(which topic, which difficulty) based on persisted state (mastery
history), and the loop runs autonomously across multiple turns without
the caller re-implementing the policy each time.

Mastery model: an exponential moving average (EMA) of correctness per
topic, biased toward recency, combined with a simple "overdue" boost so
topics that haven't been reviewed in a while resurface even if mastery
is currently high (a lightweight nod to spaced repetition).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Chunk, MasteryRecord, Topic

logger = logging.getLogger(__name__)

_EMA_ALPHA = 0.35  # weight given to the most recent attempt
_MASTERY_EASY_THRESHOLD = 0.75
_MASTERY_HARD_THRESHOLD = 0.35


@dataclass
class PlanDecision:
    topic: Topic
    difficulty: str
    reason: str


class TutorAgent:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    # --- PLAN ---
    def plan_next_topic(self) -> PlanDecision | None:
        topics = self.db.query(Topic).filter(Topic.owner_id == self.user_id).all()
        if not topics:
            return None

        records_by_topic = {
            r.topic_id: r
            for r in self.db.query(MasteryRecord).filter(MasteryRecord.user_id == self.user_id).all()
        }

        now = datetime.utcnow()
        scored: list[tuple[float, Topic, MasteryRecord | None]] = []
        for topic in topics:
            record = records_by_topic.get(topic.id)
            if record is None:
                # Never studied: highest priority so every topic gets seen at least once.
                priority = 1.0
            else:
                staleness_days = (now - record.last_reviewed_at).days if record.last_reviewed_at else 999
                staleness_boost = min(staleness_days / 14.0, 0.5)  # caps so old-but-mastered topics don't dominate
                priority = (1.0 - record.mastery_score) * 0.8 + staleness_boost
            scored.append((priority, topic, record))

        scored.sort(key=lambda t: t[0], reverse=True)
        best_priority, best_topic, best_record = scored[0]

        if best_record is None:
            difficulty = "easy"
            reason = "New topic, not yet attempted."
        elif best_record.mastery_score >= _MASTERY_EASY_THRESHOLD:
            difficulty = "hard"
            reason = f"Mastery is high ({best_record.mastery_score:.2f}); raising difficulty."
        elif best_record.mastery_score <= _MASTERY_HARD_THRESHOLD:
            difficulty = "easy"
            reason = f"Mastery is low ({best_record.mastery_score:.2f}); reinforcing fundamentals."
        else:
            difficulty = "medium"
            reason = f"Mastery is moderate ({best_record.mastery_score:.2f})."

        return PlanDecision(topic=best_topic, difficulty=difficulty, reason=reason)

    # --- GENERATE support: pick a representative chunk for the planned topic ---
    def pick_chunk_for_topic(self, topic_id: int) -> Chunk | None:
        chunks = self.db.query(Chunk).filter(Chunk.topic_id == topic_id).all()
        if not chunks:
            return None
        import random

        return random.choice(chunks)

    # --- EVALUATE + UPDATE ---
    def record_attempt_and_update_mastery(self, topic_id: int, is_correct: bool) -> float:
        record = (
            self.db.query(MasteryRecord)
            .filter(MasteryRecord.user_id == self.user_id, MasteryRecord.topic_id == topic_id)
            .first()
        )
        score_signal = 1.0 if is_correct else 0.0

        if record is None:
            record = MasteryRecord(
                user_id=self.user_id,
                topic_id=topic_id,
                mastery_score=score_signal,
                attempts_count=1,
                last_reviewed_at=datetime.utcnow(),
            )
            self.db.add(record)
        else:
            record.mastery_score = _EMA_ALPHA * score_signal + (1 - _EMA_ALPHA) * record.mastery_score
            record.attempts_count += 1
            record.last_reviewed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(record)
        logger.info(
            "Updated mastery for user=%s topic=%s -> %.3f (attempts=%s)",
            self.user_id,
            topic_id,
            record.mastery_score,
            record.attempts_count,
        )
        return record.mastery_score

    # --- REPLAN convenience ---
    def recommend_next_topic_name(self) -> str | None:
        decision = self.plan_next_topic()
        return decision.topic.name if decision else None
