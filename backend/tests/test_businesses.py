"""
backend/tests/test_businesses.py — Phase 6 Business Management Tests
=====================================================================
Tests (per Phase 6 verification gate in PROJECT_PLAN.md):
    1. Authenticated user can create a business → 201.
    2. Created business is returned with correct fields.
    3. List businesses returns only the current user's businesses.
    4. GET /api/businesses/{id} returns 200 for the owner.
    5. *** SECURITY GATE ***: User B's JWT returns 403 when accessing User A's business.
    6. Unauthenticated request returns 403.
    7. Creating two businesses — both appear in the list.
    8. An empty list is returned for a user with no businesses.

All tests use an in-memory SQLite database — no MySQL connection needed.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite test database (same pattern as test_auth.py)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_and_token(email: str, name: str = "Test User") -> str:
    """Register a user and return their JWT token."""
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "TestPass123", "full_name": name},
    )
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    return resp.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


_BUSINESS_PAYLOAD = {
    "business_name": "Rajesh Jewellers",
    "owner_name": "Rajesh Mehta",
    "email": "contact@rajeshjewellers.in",
    "phone": "+91-9876543210",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_create_business_returns_201():
    """An authenticated user can create a business and gets 201."""
    token = _register_and_token("user@test.com")
    response = client.post(
        "/api/businesses",
        json=_BUSINESS_PAYLOAD,
        headers=_auth_headers(token),
    )
    assert response.status_code == 201, response.text


def test_create_business_response_has_correct_fields():
    """Created business response contains all required fields."""
    token = _register_and_token("user@test.com")
    resp = client.post(
        "/api/businesses",
        json=_BUSINESS_PAYLOAD,
        headers=_auth_headers(token),
    ).json()

    assert resp["business_name"] == _BUSINESS_PAYLOAD["business_name"]
    assert resp["owner_name"] == _BUSINESS_PAYLOAD["owner_name"]
    assert resp["email"] == _BUSINESS_PAYLOAD["email"]
    assert resp["phone"] == _BUSINESS_PAYLOAD["phone"]
    assert isinstance(resp["business_id"], int)
    assert resp["business_id"] >= 1


def test_list_businesses_returns_own_only():
    """
    ISOLATION TEST: A user's business list only contains their OWN businesses.
    User A creates a business; User B's list must be empty.
    """
    token_a = _register_and_token("user_a@test.com", "User A")
    token_b = _register_and_token("user_b@test.com", "User B")

    # User A creates a business
    client.post("/api/businesses", json=_BUSINESS_PAYLOAD, headers=_auth_headers(token_a))

    # User B's list must be empty
    resp_b = client.get("/api/businesses", headers=_auth_headers(token_b))
    assert resp_b.status_code == 200, resp_b.text
    assert resp_b.json() == [], (
        "User B should see an empty list — not User A's businesses!"
    )

    # User A's list must contain exactly 1 business
    resp_a = client.get("/api/businesses", headers=_auth_headers(token_a))
    assert resp_a.status_code == 200, resp_a.text
    assert len(resp_a.json()) == 1


def test_get_business_by_id_owner_returns_200():
    """The owner can retrieve their business by ID → 200."""
    token = _register_and_token("owner@test.com")
    created = client.post(
        "/api/businesses", json=_BUSINESS_PAYLOAD, headers=_auth_headers(token)
    ).json()
    business_id = created["business_id"]

    response = client.get(f"/api/businesses/{business_id}", headers=_auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()["business_id"] == business_id


def test_cross_tenant_access_returns_403():
    """
    *** CORE SECURITY GATE ***
    User B's JWT must return HTTP 403 when accessing User A's business_id.
    This test verifies the multi-tenancy isolation rule (PROJECT_RULES.md Rule 11).
    """
    token_a = _register_and_token("owner_a@test.com", "Owner A")
    token_b = _register_and_token("thief_b@test.com", "Thief B")

    # User A creates a business
    business_a = client.post(
        "/api/businesses", json=_BUSINESS_PAYLOAD, headers=_auth_headers(token_a)
    ).json()
    business_id_a = business_a["business_id"]

    # User B attempts to access User A's business with their own token
    response = client.get(
        f"/api/businesses/{business_id_a}",
        headers=_auth_headers(token_b),
    )
    assert response.status_code == 403, (
        f"SECURITY VIOLATION: User B got {response.status_code} instead of 403 "
        f"when accessing User A's business_id={business_id_a}!"
    )


def test_unauthenticated_request_returns_403():
    """Accessing /api/businesses without a token returns 403."""
    response = client.get("/api/businesses")
    assert response.status_code == 403, response.text


def test_create_business_unauthenticated_returns_403():
    """Creating a business without a token returns 403."""
    response = client.post("/api/businesses", json=_BUSINESS_PAYLOAD)
    assert response.status_code == 403, response.text


def test_multiple_businesses_all_in_list():
    """A user who creates 2 businesses sees both in the list."""
    token = _register_and_token("multi@test.com")
    client.post(
        "/api/businesses",
        json={**_BUSINESS_PAYLOAD, "business_name": "Gold Palace"},
        headers=_auth_headers(token),
    )
    client.post(
        "/api/businesses",
        json={**_BUSINESS_PAYLOAD, "business_name": "Silver Shoppe"},
        headers=_auth_headers(token),
    )
    resp = client.get("/api/businesses", headers=_auth_headers(token))
    assert resp.status_code == 200
    names = [b["business_name"] for b in resp.json()]
    assert "Gold Palace" in names
    assert "Silver Shoppe" in names


def test_empty_list_for_new_user():
    """A newly registered user with no businesses gets an empty list → 200."""
    token = _register_and_token("fresh@test.com")
    resp = client.get("/api/businesses", headers=_auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_nonexistent_business_id_returns_403():
    """Requesting a business_id that doesn't exist returns 403 (not 404)."""
    token = _register_and_token("nobody@test.com")
    response = client.get("/api/businesses/99999", headers=_auth_headers(token))
    assert response.status_code == 403, (
        "Non-existent business_id must return 403 to prevent enumeration attacks"
    )
