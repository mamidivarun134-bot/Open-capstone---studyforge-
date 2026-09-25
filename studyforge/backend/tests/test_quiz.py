from app.models.models import Chunk
from app.services.llm import LLMClient, parse_quiz_json
from app.services.quiz import generate_question


def _fake_chunk(text: str) -> Chunk:
    c = Chunk(id=1, document_id=1, chunk_index=0, text=text, source_method="text", vector_row=0)
    return c


def test_generate_question_uses_extractive_fallback_without_api_key():
    llm_client = LLMClient()
    assert llm_client.is_configured is False  # ANTHROPIC_API_KEY is empty in the test env

    chunk = _fake_chunk(
        "The mitochondria is the powerhouse of the cell because it produces ATP through respiration."
    )
    question = generate_question(chunk, difficulty="medium", llm_client=llm_client)

    assert question.method == "extractive_fallback"
    assert len(question.options) == 4
    assert 0 <= question.correct_index < 4
    assert question.options[question.correct_index] in question.question_text or "blank" in question.question_text.lower()


def test_parse_quiz_json_valid():
    raw = '{"question": "What is 2+2?", "options": ["3", "4", "5", "6"], "correct_index": 1, "explanation": "Basic math."}'
    parsed = parse_quiz_json(raw)
    assert parsed is not None
    assert parsed["correct_index"] == 1


def test_parse_quiz_json_rejects_wrong_option_count():
    raw = '{"question": "Q?", "options": ["a", "b"], "correct_index": 0, "explanation": "e"}'
    assert parse_quiz_json(raw) is None


def test_parse_quiz_json_rejects_malformed_json():
    assert parse_quiz_json("not json at all") is None


def test_parse_quiz_json_rejects_out_of_range_index():
    raw = '{"question": "Q?", "options": ["a", "b", "c", "d"], "correct_index": 9, "explanation": "e"}'
    assert parse_quiz_json(raw) is None
