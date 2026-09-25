from tests.pdf_fixture import make_simple_pdf_bytes


def _upload_sample_document(client, auth_headers):
    pdf_bytes = make_simple_pdf_bytes(
        [
            "Photosynthesis converts light energy into chemical energy.",
            "Chlorophyll absorbs sunlight inside chloroplasts.",
            "Mitochondria produce ATP through cellular respiration.",
            "The Krebs cycle occurs inside the mitochondrial matrix.",
        ]
    )
    resp = client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("biology_notes.pdf", pdf_bytes, "application/pdf")},
    )
    return resp


def test_full_study_flow(client, auth_headers):
    upload_resp = _upload_sample_document(client, auth_headers)
    assert upload_resp.status_code == 201
    doc = upload_resp.json()
    assert doc["status"] == "ready"
    assert doc["page_count"] == 1

    # List documents.
    list_resp = client.get("/api/documents", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Ask a grounded question -- should retrieve relevant chunks even without an LLM key.
    ask_resp = client.post(
        "/api/qa/ask",
        headers=auth_headers,
        json={"question": "What produces ATP in the cell?"},
    )
    assert ask_resp.status_code == 200
    ask_data = ask_resp.json()
    assert ask_data["generation_method"] in ("extractive_fallback", "llm")
    assert len(ask_data["citations"]) > 0

    # Ask something unrelated to the material entirely.
    unrelated_resp = client.post(
        "/api/qa/ask",
        headers=auth_headers,
        json={"question": "What is the capital of Australia?"},
    )
    assert unrelated_resp.status_code == 200

    # Run one full adaptive-quiz cycle.
    next_q_resp = client.post("/api/quiz/next", headers=auth_headers)
    assert next_q_resp.status_code == 200
    question = next_q_resp.json()
    assert len(question["options"]) == 4

    answer_resp = client.post(
        "/api/quiz/answer",
        headers=auth_headers,
        json={"question_id": question["id"], "selected_option_index": 0},
    )
    assert answer_resp.status_code == 200
    answer_data = answer_resp.json()
    assert "is_correct" in answer_data
    assert 0.0 <= answer_data["updated_mastery"] <= 1.0

    # Dashboard should now reflect at least one attempt.
    dashboard_resp = client.get("/api/dashboard/mastery", headers=auth_headers)
    assert dashboard_resp.status_code == 200
    dashboard_data = dashboard_resp.json()
    assert len(dashboard_data["topics"]) >= 1
    assert any(t["attempts_count"] > 0 for t in dashboard_data["topics"])


def test_ask_without_any_documents_returns_no_match(client):
    email = "nodoc@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    login = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post("/api/qa/ask", headers=headers, json={"question": "Anything?"})
    assert resp.status_code == 200
    assert resp.json()["generation_method"] == "no_match"


def test_quiz_next_without_documents_returns_400(client):
    email = "noquiz@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    login = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post("/api/quiz/next", headers=headers)
    assert resp.status_code == 400
