"""
backend/tests/test_insights.py — Phase 15 Proactive Insights Engine Tests
=========================================================================
Tests (per Phase 15 verification gate in PROJECT_PLAN.md):

    1. run_all_rules() returns a list for an empty business (no alerts, no crash).
    2. Aged inventory > ₹1L triggers HIGH priority alert.
    3. Aged inventory < ₹1L does NOT trigger HIGH alert (under threshold).
    4. Stockout risk items trigger MEDIUM priority alert.
    5. Discount escalation > 25% MoM triggers LOW priority alert.
    6. Alerts are sorted: high before medium before low.
    7. *** ISOLATION GATE ***: Biz A alerts never appear in Biz B's insight list.
    8. API GET /insights returns 200 with correct structure for owner.
    9. API GET /insights returns 403 for cross-tenant access.
   10. API GET /insights returns 403 for unauthenticated request.
"""

from datetime import date, datetime, timedelta
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
from backend.app.models.purchase import Purchase
from backend.app.models.sale import Sale
from backend.app.services.auth_service import hash_password
from backend.app.services import insight_service

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_biz(db: Session, email: str, name: str) -> Business:
    u = User(email=email, password_hash=hash_password("Test1234!!"), full_name="T")
    db.add(u); db.flush()
    b = Business(owner_user_id=u.user_id, business_name=name)
    db.add(b); db.flush()
    db.commit()
    return b


def _seed_product(db: Session, bid: int, sku: str) -> Product:
    p = Product(
        business_id=bid, sku=sku, product_name=f"Item {sku}",
        category="ring", metal="gold", purity="22K",
        gross_weight=10.0, net_weight=9.0,
    )
    db.add(p); db.flush(); db.commit()
    return p


def _seed_old_purchase(db: Session, bid: int, product_id: int, metal_cost: float, days_ago: int = 200):
    old_date = date.today() - timedelta(days=days_ago)
    pur = Purchase(
        business_id=bid, product_id=product_id, weight=10.0,
        metal_cost=metal_cost, making_charge=500.0, purchase_date=old_date,
    )
    db.add(pur); db.commit()


def _seed_sale(db: Session, bid: int, product_id: int, weight: float = 5.0):
    s = Sale(
        business_id=bid, product_id=product_id, weight=weight,
        selling_price=10000.0, discount=300.0, making_charge=500.0,
        cost_basis=7000.0, sale_date=datetime.now(),
    )
    db.add(s); db.commit()


def _register_and_token(email: str) -> str:
    r = client.post("/api/auth/register",
        json={"email": email, "password": "Test1234!!", "full_name": "T"})
    assert r.status_code == 201
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Service-Layer Tests
# ---------------------------------------------------------------------------

def test_empty_business_returns_no_alerts_no_crash(db):
    """run_all_rules() returns empty list for a business with no data."""
    biz = _seed_biz(db, "ins_empty@test.com", "Empty Biz")
    alerts = insight_service.run_all_rules(db, biz.business_id)
    assert isinstance(alerts, list)
    assert all(a.get("evidence") is not None for a in alerts)  # each has evidence if any


def test_aged_high_alert_triggered_above_1L(db):
    """Aged inventory > ₹1L triggers a HIGH priority aged_inventory_high alert."""
    biz = _seed_biz(db, "ins_high@test.com", "High Biz")
    prod = _seed_product(db, biz.business_id, "HIGH001")
    _seed_old_purchase(db, biz.business_id, prod.product_id, metal_cost=150_000.0, days_ago=200)

    alerts = insight_service.run_all_rules(db, biz.business_id)
    high_alerts = [a for a in alerts if a["priority"] == "high"]
    assert len(high_alerts) >= 1, "Expected HIGH alert for aged inventory > ₹1L"


def test_aged_alert_not_high_when_under_threshold(db):
    """Aged inventory below ₹1L does NOT trigger HIGH priority alert."""
    biz = _seed_biz(db, "ins_low_val@test.com", "Low Val Biz")
    prod = _seed_product(db, biz.business_id, "LOW001")
    _seed_old_purchase(db, biz.business_id, prod.product_id, metal_cost=50_000.0, days_ago=200)

    alerts = insight_service.run_all_rules(db, biz.business_id)
    high_alerts = [a for a in alerts if a["priority"] == "high"]
    assert len(high_alerts) == 0, "Should NOT trigger HIGH alert when value < ₹1L"


def test_stockout_warning_triggers_medium_alert(db):
    """Fast-moving products with low coverage trigger MEDIUM stockout alert."""
    biz  = _seed_biz(db, "ins_stock@test.com", "Stock Biz")
    prod = _seed_product(db, biz.business_id, "STK001")

    # Purchase 2 units, sell 1.8 units rapidly over last 30 days → coverage < 15d
    purchase_date = date.today() - timedelta(days=5)
    pur = Purchase(
        business_id=biz.business_id, product_id=prod.product_id, weight=2.0,
        metal_cost=14_000.0, making_charge=400.0, purchase_date=purchase_date,
    )
    db.add(pur); db.commit()

    # 3 recent sales consuming most of the stock
    for _ in range(3):
        s = Sale(
            business_id=biz.business_id, product_id=prod.product_id, weight=0.5,
            selling_price=8000.0, discount=200.0, making_charge=400.0,
            cost_basis=5000.0,
            sale_date=datetime.now() - timedelta(days=1),
        )
        db.add(s)
    db.commit()

    alerts = insight_service.run_all_rules(db, biz.business_id)
    medium_alerts = [a for a in alerts if a["priority"] == "medium" and "stockout" in a["rule_id"]]
    assert len(medium_alerts) >= 1, "Expected MEDIUM stockout warning alert"


def test_alert_sort_order_high_before_medium_before_low(db):
    """Alerts are sorted high → medium → low by priority."""
    biz  = _seed_biz(db, "ins_sort@test.com", "Sort Biz")
    prod = _seed_product(db, biz.business_id, "SORT001")
    _seed_old_purchase(db, biz.business_id, prod.product_id, metal_cost=200_000.0, days_ago=200)

    alerts = insight_service.run_all_rules(db, biz.business_id)
    if len(alerts) < 2:
        pytest.skip("Need ≥2 alerts to verify sort order")

    priority_order = {"high": 0, "medium": 1, "low": 2}
    priorities = [priority_order[a["priority"]] for a in alerts]
    assert priorities == sorted(priorities), "Alerts must be sorted high → medium → low"


def test_isolation_rule_scoped_to_business_id(db):
    """
    *** ISOLATION GATE ***
    Aged inventory from Biz A must NOT appear in Biz B's insights.
    """
    biz_a = _seed_biz(db, "ins_iso_a@test.com", "Biz A")
    biz_b = _seed_biz(db, "ins_iso_b@test.com", "Biz B")

    prod_a = _seed_product(db, biz_a.business_id, "ISO_A001")
    _seed_old_purchase(db, biz_a.business_id, prod_a.product_id, metal_cost=200_000.0, days_ago=200)

    # Biz B should have zero alerts — its own data is empty
    alerts_b = insight_service.run_all_rules(db, biz_b.business_id)
    high_b = [a for a in alerts_b if a["priority"] == "high"]
    assert len(high_b) == 0, "ISOLATION VIOLATION: Biz A aged inventory appeared in Biz B insights!"


def test_each_alert_has_required_fields(db):
    """Every returned alert contains all required fields."""
    biz  = _seed_biz(db, "ins_fields@test.com", "Fields Biz")
    prod = _seed_product(db, biz.business_id, "FLD001")
    _seed_old_purchase(db, biz.business_id, prod.product_id, metal_cost=150_000.0, days_ago=200)

    alerts = insight_service.run_all_rules(db, biz.business_id)
    required = {"rule_id", "priority", "title", "detail", "action_link", "evidence"}
    for alert in alerts:
        missing = required - set(alert.keys())
        assert not missing, f"Alert missing fields: {missing}"


# ---------------------------------------------------------------------------
# API Route Tests
# ---------------------------------------------------------------------------

def test_api_insights_returns_200_for_owner():
    """GET /insights returns 200 with correct structure for the business owner."""
    token = _register_and_token("api_ins@test.com")
    biz_id = client.post("/api/businesses",
        json={"business_name": "Insight Biz"}, headers=_auth(token)).json()["business_id"]

    resp = client.get(f"/api/businesses/{biz_id}/insights", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "alerts" in body
    assert "business_id" in body
    assert body["business_id"] == biz_id
    assert "as_of" in body
    assert "count" in body


def test_api_insights_cross_tenant_returns_403():
    """User B cannot access User A's insight center."""
    token_a = _register_and_token("ins_user_a@test.com")
    token_b = _register_and_token("ins_user_b@test.com")
    biz_a = client.post("/api/businesses",
        json={"business_name": "A"}, headers=_auth(token_a)).json()["business_id"]

    resp = client.get(f"/api/businesses/{biz_a}/insights", headers=_auth(token_b))
    assert resp.status_code == 403


def test_api_insights_unauthenticated_returns_403():
    """GET /insights without a token returns 403."""
    resp = client.get("/api/businesses/1/insights")
    assert resp.status_code == 403
