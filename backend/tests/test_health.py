"""
tests/test_health.py — Phase 4 Verification Gate
==================================================
Verifies:
    1. GET /health returns HTTP 200.
    2. Response body contains {"status": "ok"|"degraded", "database": bool}.
    3. The "version" field is present.

Run:
    pytest backend/tests/test_health.py -v
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint_returns_200():
    """GET /health should always return 200 OK (even if DB is degraded)."""
    response = client.get("/health")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. Body: {response.text}"
    )


def test_health_response_has_required_fields():
    """Response must contain 'status', 'database', and 'version' keys."""
    response = client.get("/health")
    body = response.json()

    assert "status" in body, "Response missing 'status' field"
    assert "database" in body, "Response missing 'database' field"
    assert "version" in body, "Response missing 'version' field"


def test_health_status_is_valid_string():
    """'status' must be either 'ok' or 'degraded'."""
    response = client.get("/health")
    status = response.json()["status"]
    assert status in ("ok", "degraded"), (
        f"'status' must be 'ok' or 'degraded', got: {status!r}"
    )


def test_health_database_is_bool():
    """'database' field must be a boolean."""
    response = client.get("/health")
    db_field = response.json()["database"]
    assert isinstance(db_field, bool), (
        f"'database' must be bool, got {type(db_field).__name__}"
    )


def test_swagger_ui_loads():
    """Swagger UI (/docs) must return 200."""
    response = client.get("/docs")
    assert response.status_code == 200, (
        f"Swagger UI (/docs) returned {response.status_code}"
    )
