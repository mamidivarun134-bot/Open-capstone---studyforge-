from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.models.database import get_db
from app.models.models import MasteryRecord, Topic, User
from app.schemas.schemas import DashboardResponse, TopicMastery

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/mastery", response_model=DashboardResponse)
def get_mastery(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> DashboardResponse:
    topics = db.query(Topic).filter(Topic.owner_id == current_user.id).all()
    records = {r.topic_id: r for r in db.query(MasteryRecord).filter(MasteryRecord.user_id == current_user.id).all()}

    topic_masteries: list[TopicMastery] = []
    for topic in topics:
        record = records.get(topic.id)
        topic_masteries.append(
            TopicMastery(
                topic_id=topic.id,
                topic_name=topic.name,
                mastery_score=round(record.mastery_score, 4) if record else 0.0,
                attempts_count=record.attempts_count if record else 0,
                last_reviewed_at=record.last_reviewed_at if record else None,
            )
        )

    topic_masteries.sort(key=lambda t: t.mastery_score)
    overall = sum(t.mastery_score for t in topic_masteries) / len(topic_masteries) if topic_masteries else 0.0
    weakest = topic_masteries[0].topic_name if topic_masteries else None

    return DashboardResponse(topics=topic_masteries, overall_mastery=round(overall, 4), weakest_topic=weakest)
