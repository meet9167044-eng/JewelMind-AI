"""
backend/tests/test_copilot.py — Phase 14 AI Copilot & Tool Calling Tests
========================================================================
Tests (per Phase 14 verification gate in PROJECT_PLAN.md):

    1. execute_tool("analyze_profit_change") executes deterministically and includes business_id closure.
    2. execute_tool("analyze_inventory") retrieves ageing/dead stock for the target business.
    3. execute_tool("analyze_metal_exposure") calculates WAR and exposure.
    4. execute_tool("simulate_metal_change") calculates rate-shift simulation delta.
    5. *** ISOLATION GATE ***: execute_tool for Biz A never returns data from Biz B.
    6. System prompt guardrails generator includes business_name string.
    7. Fail-safe: ask() returns setup message if LLM_API_KEY is missing/empty.
    8. API POST /copilot/ask returns 200 with response_text structure.
    9. API POST /copilot/ask cross-tenant access returns 403.
   10. API POST /copilot/ask unauthenticated returns 403.
"""

from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.user import User
from backend.app.models.business import Business
from backend.app.models.product import Product
from backend.app.models.metal_rate import MetalRate
from backend.app.services.auth_service import hash_password
from backend.app.services import copilot_service

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


@pytest.fixture
def db() -> Session:
    s = TestSessionLocal()
    yield s
    s.close()


client = TestClient(app)


def _seed_biz(db: Session, email: str, name: str) -> Business:
    u = User(email=email, password_hash=hash_password("Test1234!!"), full_name="T")
    db.add(u); db.flush()
    b = Business(owner_user_id=u.user_id, business_name=name)
    db.add(b); db.flush()
    db.commit()
    return b


def _seed_metal_rate(db: Session):
    rate = MetalRate(rate_date=date(2026, 7, 30), gold_24k=7200.0, gold_22k=6600.0, silver=85.0)
    db.add(rate); db.commit()


def _register_and_token(email: str) -> str:
    r = client.post("/api/auth/register",
        json={"email": email, "password": "Test1234!!", "full_name": "T"})
    assert r.status_code == 201
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Tool Execution Tests (backend execution layer)
# ---------------------------------------------------------------------------

def test_execute_tool_profit_change(db):
    """execute_tool("analyze_profit_change") executes deterministically."""
    biz = _seed_biz(db, "cp_prof@test.com", "Mehta Gold")
    res = copilot_service.execute_tool(
        "analyze_profit_change",
        {"target_month": "2026-06", "baseline_month": "2026-05"},
        biz.business_id,
        db
    )
    assert res["tool"] == "analyze_profit_change"
    assert res["scoped_to_business_id"] == biz.business_id
    assert "formula" in res
    assert "drivers" in res["result"]


def test_execute_tool_inventory(db):
    """execute_tool("analyze_inventory") returns stock analysis."""
    biz = _seed_biz(db, "cp_inv@test.com", "Rajesh Jewellers")
    res = copilot_service.execute_tool(
        "analyze_inventory",
        {"category": "ring"},
        biz.business_id,
        db
    )
    assert res["tool"] == "analyze_inventory"
    assert "buckets" in res["result"]
    assert "dead_stock" in res["result"]


def test_execute_tool_metal_exposure(db):
    """execute_tool("analyze_metal_exposure") calculates WAR and exposure."""
    _seed_metal_rate(db)
    biz = _seed_biz(db, "cp_metal@test.com", "Silver House")
    res = copilot_service.execute_tool(
        "analyze_metal_exposure",
        {"metal": "gold"},
        biz.business_id,
        db
    )
    assert res["tool"] == "analyze_metal_exposure"
    assert "war" in res["result"]
    assert "valuation_exposure" in res["result"]


def test_execute_tool_simulate_metal_change(db):
    """execute_tool("simulate_metal_change") calculates rate-shift simulation delta."""
    _seed_metal_rate(db)
    biz = _seed_biz(db, "cp_sim@test.com", "Gold Sim")
    res = copilot_service.execute_tool(
        "simulate_metal_change",
        {"metal": "gold", "change_percent": 10.0},
        biz.business_id,
        db
    )
    assert res["tool"] == "simulate_metal_change"
    assert "delta_value" in res["result"]


def test_isolation_tool_execution_scoped_to_business_id(db):
    """
    *** ISOLATION GATE ***
    Tool execution for Business A must NEVER return products from Business B.
    """
    biz_a = _seed_biz(db, "cop_iso_a@test.com", "Biz A")
    biz_b = _seed_biz(db, "cop_iso_b@test.com", "Biz B")

    # Add product to Biz A
    p_a = Product(business_id=biz_a.business_id, sku="A001", product_name="Ring A", category="ring", metal="gold", purity="22K", gross_weight=10, net_weight=9)
    db.add(p_a); db.commit()

    # Query inventory for Biz B via tool handler
    res_b = copilot_service.execute_tool("analyze_inventory", {}, biz_b.business_id, db)
    assert res_b["result"]["total_items"] == 0, "ISOLATION VIOLATION: Biz B tool returned Biz A items!"


def test_system_prompt_includes_business_name():
    """System prompt includes the exact business_name for advisor context."""
    prompt = copilot_service.build_system_prompt("Mehta Jewels")
    assert "Mehta Jewels" in prompt
    assert "NEVER CALCULATE OR INVENT NUMBERS" in prompt


def test_ask_failsafe_when_api_key_missing():
    """ask() returns safe setup notice if LLM_API_KEY is not set."""
    copilot_service.LLM_API_KEY = ""
    res = copilot_service.ask("Why did profit fall?", 1, "Test Biz", None) # type: ignore
    assert "LLM API key" in res["response_text"]
    assert res["evidence"] is None


# ---------------------------------------------------------------------------
# API Route Tests
# ---------------------------------------------------------------------------

def test_api_copilot_ask_returns_200():
    """POST /api/businesses/{id}/copilot/ask returns 200."""
    token = _register_and_token("api_cop@test.com")
    biz_id = client.post("/api/businesses", json={"business_name": "Copilot Biz"}, headers=_auth(token)).json()["business_id"]

    copilot_service.LLM_API_KEY = "" # ensure fail-safe path triggers cleanly
    resp = client.post(f"/api/businesses/{biz_id}/copilot/ask", json={"question": "What is my gold exposure?"}, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "response_text" in body


def test_api_copilot_cross_tenant_returns_403():
    """User B cannot ask questions about User A's business."""
    token_a = _register_and_token("cop_user_a@test.com")
    token_b = _register_and_token("cop_user_b@test.com")
    biz_a = client.post("/api/businesses", json={"business_name": "A"}, headers=_auth(token_a)).json()["business_id"]

    resp = client.post(f"/api/businesses/{biz_a}/copilot/ask", json={"question": "Show profit"}, headers=_auth(token_b))
    assert resp.status_code == 403


def test_api_copilot_unauthenticated_returns_403():
    """Request without token returns 403."""
    resp = client.post("/api/businesses/1/copilot/ask", json={"question": "Show profit"})
    assert resp.status_code == 403
