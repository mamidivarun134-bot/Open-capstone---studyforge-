import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_TEST_DIR = tempfile.mkdtemp(prefix="studyforge_test_")
os.environ["ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR}/test.db"
os.environ["RAW_DATA_DIR"] = f"{_TEST_DIR}/raw"
os.environ["VECTOR_STORE_DIR"] = f"{_TEST_DIR}/vector_store"
os.environ["ANTHROPIC_API_KEY"] = ""  # force fallback paths in tests -- deterministic, no network calls

from app.models.database import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    yield
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    email = "student@example.com"
    password = "supersecret123"
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    if resp.status_code == 409:
        resp = client.post("/api/auth/login", data={"username": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
