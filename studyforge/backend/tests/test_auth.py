def test_register_and_login(client):
    resp = client.post("/api/auth/register", json={"email": "alice@example.com", "password": "password123"})
    assert resp.status_code == 201
    assert "access_token" in resp.json()

    resp = client.post("/api/auth/login", data={"username": "alice@example.com", "password": "password123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_duplicate_registration_rejected(client):
    client.post("/api/auth/register", json={"email": "bob@example.com", "password": "password123"})
    resp = client.post("/api/auth/register", json={"email": "bob@example.com", "password": "password123"})
    assert resp.status_code == 409


def test_login_wrong_password_rejected(client):
    client.post("/api/auth/register", json={"email": "carol@example.com", "password": "password123"})
    resp = client.post("/api/auth/login", data={"username": "carol@example.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_protected_route_requires_token(client):
    resp = client.get("/api/documents")
    assert resp.status_code == 401


def test_short_password_rejected(client):
    resp = client.post("/api/auth/register", json={"email": "dave@example.com", "password": "short"})
    assert resp.status_code == 422
