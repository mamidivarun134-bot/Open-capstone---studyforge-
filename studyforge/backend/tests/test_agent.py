from app.agents.tutor_agent import TutorAgent
from app.models.database import session_scope
from app.models.models import Topic, User
from app.core.security import hash_password


def _make_user_with_topics(db, email, topic_names):
    user = User(email=email, hashed_password=hash_password("password123"))
    db.add(user)
    db.flush()
    topics = []
    for name in topic_names:
        t = Topic(owner_id=user.id, name=name)
        db.add(t)
        topics.append(t)
    db.flush()
    return user, topics


def test_plan_returns_none_with_no_topics():
    with session_scope() as db:
        user = User(email="empty@example.com", hashed_password=hash_password("password123"))
        db.add(user)
        db.flush()
        agent = TutorAgent(db, user.id)
        assert agent.plan_next_topic() is None


def test_plan_prioritizes_never_studied_topic():
    with session_scope() as db:
        user, topics = _make_user_with_topics(db, "planner@example.com", ["Topic A", "Topic B"])
        agent = TutorAgent(db, user.id)
        decision = agent.plan_next_topic()
        assert decision is not None
        assert decision.topic.id in {t.id for t in topics}
        assert decision.difficulty == "easy"


def test_mastery_increases_on_correct_answers():
    with session_scope() as db:
        user, topics = _make_user_with_topics(db, "mastery@example.com", ["Only Topic"])
        agent = TutorAgent(db, user.id)
        topic_id = topics[0].id

        score1 = agent.record_attempt_and_update_mastery(topic_id, is_correct=True)
        score2 = agent.record_attempt_and_update_mastery(topic_id, is_correct=True)
        score3 = agent.record_attempt_and_update_mastery(topic_id, is_correct=False)

        assert score1 == 1.0
        assert score2 == 1.0
        assert score3 < score2  # a wrong answer should pull the EMA down


def test_high_mastery_increases_difficulty():
    with session_scope() as db:
        user, topics = _make_user_with_topics(db, "hard@example.com", ["Mastered Topic"])
        agent = TutorAgent(db, user.id)
        topic_id = topics[0].id

        for _ in range(5):
            agent.record_attempt_and_update_mastery(topic_id, is_correct=True)

        decision = agent.plan_next_topic()
        assert decision.difficulty == "hard"


def test_low_mastery_keeps_difficulty_easy():
    with session_scope() as db:
        user, topics = _make_user_with_topics(db, "struggling@example.com", ["Weak Topic"])
        agent = TutorAgent(db, user.id)
        topic_id = topics[0].id

        for _ in range(5):
            agent.record_attempt_and_update_mastery(topic_id, is_correct=False)

        decision = agent.plan_next_topic()
        assert decision.difficulty == "easy"
