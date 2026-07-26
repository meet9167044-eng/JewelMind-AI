"""
backend/tests/test_auth.py — Phase 5 Auth Verification Tests
=============================================================
Tests (per Phase 5 verification gate in PROJECT_PLAN.md):
    1. Successful registration returns HTTP 201 + JWT token.
    2. Duplicate email registration returns HTTP 409.
    3. Successful login returns HTTP 200 + JWT token.
    4. Invalid password returns HTTP 401.
    5. Unknown email returns HTTP 401.
    6. GET /api/auth/me with valid token returns user profile.
    7. GET /api/auth/me with bad token returns HTTP 401.
    8. JWT payload contains only user_id (sub) — no PII.

All tests use an in-memory SQLite database so no MySQL connection is needed.
The in-memory DB is recreated fresh for each test function.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite test database
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Override the real MySQL DB with an in-memory SQLite DB for tests."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test; drop them after."""
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


client = TestClient(app)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
_REGISTER_PAYLOAD = {
    "email": "meet@jewelmind.ai",
    "password": "SecurePass123",
    "full_name": "Meet Jain",
}


def _register_user(payload: dict | None = None) -> dict:
    """Register a user and return the response JSON."""
    return client.post("/api/auth/register", json=payload or _REGISTER_PAYLOAD).json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_register_success_returns_201():
    """Successful registration returns HTTP 201 and a token."""
    response = client.post("/api/auth/register", json=_REGISTER_PAYLOAD)
    assert response.status_code == 201, response.text
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["email"] == _REGISTER_PAYLOAD["email"]
    assert body["full_name"] == _REGISTER_PAYLOAD["full_name"]
    assert isinstance(body["user_id"], int)


def test_register_duplicate_email_returns_409():
    """Registering the same email twice returns HTTP 409 Conflict."""
    client.post("/api/auth/register", json=_REGISTER_PAYLOAD)
    response = client.post("/api/auth/register", json=_REGISTER_PAYLOAD)
    assert response.status_code == 409, response.text


def test_register_short_password_returns_422():
    """Password shorter than 8 characters is rejected with HTTP 422."""
    payload = {**_REGISTER_PAYLOAD, "password": "short"}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422, response.text


def test_login_success_returns_200():
    """Successful login returns HTTP 200 with a valid JWT."""
    client.post("/api/auth/register", json=_REGISTER_PAYLOAD)
    response = client.post(
        "/api/auth/login",
        json={"email": _REGISTER_PAYLOAD["email"], "password": _REGISTER_PAYLOAD["password"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_returns_401():
    """Wrong password returns HTTP 401 Unauthorized."""
    client.post("/api/auth/register", json=_REGISTER_PAYLOAD)
    response = client.post(
        "/api/auth/login",
        json={"email": _REGISTER_PAYLOAD["email"], "password": "WrongPassword!"},
    )
    assert response.status_code == 401, response.text


def test_login_unknown_email_returns_401():
    """Login with an email that was never registered returns HTTP 401."""
    response = client.post(
        "/api/auth/login",
        json={"email": "nobody@jewelmind.ai", "password": "whatever"},
    )
    assert response.status_code == 401, response.text


def test_get_me_with_valid_token():
    """GET /api/auth/me with a valid token returns the user's profile."""
    token = _register_user()["access_token"]
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == _REGISTER_PAYLOAD["email"]
    assert body["full_name"] == _REGISTER_PAYLOAD["full_name"]
    assert "password_hash" not in body   # password hash must never leak


def test_get_me_without_token_returns_403():
    """GET /api/auth/me without a token returns HTTP 403 (no credentials)."""
    response = client.get("/api/auth/me")
    assert response.status_code == 403, response.text


def test_get_me_with_bad_token_returns_401():
    """GET /api/auth/me with an invalid token returns HTTP 401."""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer this-is-not-a-real-jwt"},
    )
    assert response.status_code == 401, response.text


def test_jwt_payload_contains_only_user_id():
    """
    JWT payload must contain only 'sub' (user_id) and 'exp'.
    No PII (email, full_name, password_hash) must be present.
    """
    from jose import jwt as jose_jwt
    from backend.app.config import settings

    token = _register_user()["access_token"]
    payload = jose_jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert "sub" in payload, "JWT must have 'sub' claim"
    assert "exp" in payload, "JWT must have 'exp' claim"
    assert "email" not in payload, "Email must NOT be in JWT"
    assert "full_name" not in payload, "full_name must NOT be in JWT"
    assert "password" not in payload, "Password must NOT be in JWT"
    # sub must be a string representing an integer user_id
    assert str(int(payload["sub"])) == payload["sub"]
