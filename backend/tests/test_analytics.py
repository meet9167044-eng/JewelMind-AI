"""
backend/tests/test_analytics.py — Phase 8 Analytics Service Tests
==================================================================
Tests (per Phase 8 verification gate in PROJECT_PLAN.md):

    1. Revenue calculation returns correct gross/net/discount values.
    2. COGS calculation returns correct cost_basis sum.
    3. Gross Profit and Gross Margin % are correct.
    4. Making charge per gram is calculated correctly.
    5. *** ISOLATION TEST ***: Revenue for business_id=1 does NOT include
       business_id=2's sales — the core multi-tenant rule.
    6. Empty period returns zeros (not errors).
    7. compare_months returns correct delta between two months.
    8. Negative gross margin handled correctly (Scenario A from Phase 3).
    9. API endpoints return 200 with valid JWT + owned business.
    10. API endpoints return 403 for cross-tenant access.

All tests use in-memory SQLite — no MySQL connection required.
"""

import pytest
from datetime import date, datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.user import User
from backend.app.models.business import Business
from backend.app.models.product import Product
from backend.app.models.sale import Sale
from backend.app.services import analytics_service
from backend.app.services.auth_service import hash_password

# ---------------------------------------------------------------------------
# In-memory SQLite test setup
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


@pytest.fixture
def db() -> Session:
    """Direct DB session for service-level unit tests."""
    session = TestSessionLocal()
    yield session
    session.close()


client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures — seed helper
# ---------------------------------------------------------------------------

def _create_user_and_business(db: Session, email: str, business_name: str):
    """Create a user + business and return (user, business)."""
    u = User(email=email, password_hash=hash_password("Test1234"), full_name="Test")
    db.add(u)
    db.flush()
    b = Business(owner_user_id=u.user_id, business_name=business_name)
    db.add(b)
    db.flush()
    return u, b


def _create_product(db: Session, business_id: int, sku: str = "SKU001") -> Product:
    p = Product(
        business_id=business_id,
        sku=sku,
        product_name="Test Ring",
        category="ring",
        metal="gold",
        purity="22K",
        gross_weight=10.0,
        net_weight=9.0,
    )
    db.add(p)
    db.flush()
    return p


def _create_sale(
    db: Session,
    business_id: int,
    product_id: int,
    selling_price: float,
    discount: float,
    cost_basis: float,
    making_charge: float,
    weight: float,
    sale_date: date,
) -> Sale:
    s = Sale(
        business_id=business_id,
        product_id=product_id,
        sale_date=datetime.combine(sale_date, datetime.min.time()),
        quantity=1,
        weight=weight,
        selling_price=selling_price,
        making_charge=making_charge,
        discount=discount,
        cost_basis=cost_basis,
    )
    db.add(s)
    db.flush()
    return s


# ---------------------------------------------------------------------------
# Unit tests: calculate_revenue
# ---------------------------------------------------------------------------

def test_calculate_revenue_correct_values(db):
    """
    2 sales: (selling_price=1000, discount=100), (selling_price=2000, discount=200)
    Expected: gross_revenue=3000, total_discount=300, net_revenue=2700
    """
    _, biz = _create_user_and_business(db, "r@test.com", "Biz A")
    prod = _create_product(db, biz.business_id)
    _create_sale(db, biz.business_id, prod.product_id, 1000, 100, 800, 50, 5.0, date(2026, 6, 1))
    _create_sale(db, biz.business_id, prod.product_id, 2000, 200, 1600, 80, 8.0, date(2026, 6, 15))
    db.commit()

    result = analytics_service.calculate_revenue(
        db, biz.business_id, date(2026, 6, 1), date(2026, 6, 30)
    )
    assert result["gross_revenue"] == 3000.0
    assert result["total_discount"] == 300.0
    assert result["net_revenue"] == 2700.0
    assert result["transaction_count"] == 2


def test_calculate_revenue_empty_period_returns_zeros(db):
    """No sales in the period → all zeros, no error."""
    _, biz = _create_user_and_business(db, "empty@test.com", "Empty Biz")
    db.commit()

    result = analytics_service.calculate_revenue(
        db, biz.business_id, date(2026, 1, 1), date(2026, 1, 31)
    )
    assert result["gross_revenue"] == 0.0
    assert result["net_revenue"] == 0.0
    assert result["transaction_count"] == 0


# ---------------------------------------------------------------------------
# Unit tests: calculate_cogs
# ---------------------------------------------------------------------------

def test_calculate_cogs_correct_values(db):
    """
    2 sales: cost_basis 800 + 1600 = 2400
    """
    _, biz = _create_user_and_business(db, "cogs@test.com", "COGS Biz")
    prod = _create_product(db, biz.business_id)
    _create_sale(db, biz.business_id, prod.product_id, 1000, 0, 800, 50, 5.0, date(2026, 6, 1))
    _create_sale(db, biz.business_id, prod.product_id, 2000, 0, 1600, 80, 8.0, date(2026, 6, 15))
    db.commit()

    result = analytics_service.calculate_cogs(
        db, biz.business_id, date(2026, 6, 1), date(2026, 6, 30)
    )
    assert result["cogs"] == 2400.0


# ---------------------------------------------------------------------------
# Unit tests: calculate_gross_profit
# ---------------------------------------------------------------------------

def test_calculate_gross_profit_correct_values(db):
    """
    1 sale: selling_price=1000, discount=50, cost_basis=700
    Net Revenue = 950, COGS = 700, Gross Profit = 250
    Gross Margin % = (250 / 950) * 100 = 26.3158...
    """
    _, biz = _create_user_and_business(db, "gp@test.com", "GP Biz")
    prod = _create_product(db, biz.business_id)
    _create_sale(db, biz.business_id, prod.product_id, 1000, 50, 700, 80, 5.0, date(2026, 5, 10))
    db.commit()

    result = analytics_service.calculate_gross_profit(
        db, biz.business_id, date(2026, 5, 1), date(2026, 5, 31)
    )
    assert result["net_revenue"] == 950.0
    assert result["cogs"] == 700.0
    assert result["gross_profit"] == 250.0
    assert result["gross_margin_pct"] == pytest.approx((250 / 950) * 100, rel=1e-4)


def test_gross_margin_negative_handled(db):
    """
    Negative gross margin (Scenario A from Phase 3 hand-trace).
    selling_price=900, discount=50, cost_basis=1000
    Net Revenue = 850, COGS = 1000, GP = -150  (negative margin is valid)
    """
    _, biz = _create_user_and_business(db, "neg@test.com", "Neg Margin Biz")
    prod = _create_product(db, biz.business_id)
    _create_sale(db, biz.business_id, prod.product_id, 900, 50, 1000, 80, 5.0, date(2026, 6, 1))
    db.commit()

    result = analytics_service.calculate_gross_profit(
        db, biz.business_id, date(2026, 6, 1), date(2026, 6, 30)
    )
    assert result["gross_profit"] == -150.0
    assert result["gross_margin_pct"] < 0


def test_making_charge_per_gram(db):
    """
    making_charge=100, weight=10 → making_charge_per_gram = 10.0
    """
    _, biz = _create_user_and_business(db, "mc@test.com", "MC Biz")
    prod = _create_product(db, biz.business_id)
    _create_sale(db, biz.business_id, prod.product_id, 1000, 0, 800, 100, 10.0, date(2026, 6, 1))
    db.commit()

    result = analytics_service.calculate_gross_profit(
        db, biz.business_id, date(2026, 6, 1), date(2026, 6, 30)
    )
    assert result["making_charge_per_gram"] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# *** CRITICAL ISOLATION TEST ***
# ---------------------------------------------------------------------------

def test_revenue_isolation_across_businesses(db):
    """
    *** MULTI-TENANCY ISOLATION TEST ***
    Business A: 1 sale with selling_price=5000
    Business B: 1 sale with selling_price=9999

    calculate_revenue(db, business_a_id) must return 5000 — NOT include 9999.
    This verifies PROJECT_RULES.md Rule 11.
    """
    _, biz_a = _create_user_and_business(db, "owner_a@iso.com", "Business A")
    _, biz_b = _create_user_and_business(db, "owner_b@iso.com", "Business B")
    prod_a = _create_product(db, biz_a.business_id, "SKU-A")
    prod_b = _create_product(db, biz_b.business_id, "SKU-B")
    _create_sale(db, biz_a.business_id, prod_a.product_id, 5000, 0, 3000, 50, 5.0, date(2026, 6, 1))
    _create_sale(db, biz_b.business_id, prod_b.product_id, 9999, 0, 6000, 90, 9.0, date(2026, 6, 1))
    db.commit()

    result_a = analytics_service.calculate_revenue(
        db, biz_a.business_id, date(2026, 6, 1), date(2026, 6, 30)
    )
    assert result_a["gross_revenue"] == 5000.0, (
        f"ISOLATION VIOLATION: Business A revenue should be 5000 but got {result_a['gross_revenue']}!"
    )
    assert result_a["transaction_count"] == 1, (
        "ISOLATION VIOLATION: Business A should have exactly 1 transaction!"
    )


# ---------------------------------------------------------------------------
# Unit tests: compare_months
# ---------------------------------------------------------------------------

def test_compare_months_delta(db):
    """
    May: selling_price=2000, discount=0, cost_basis=1500 → GP=500
    June: selling_price=3000, discount=0, cost_basis=2000 → GP=1000
    Delta GP = 1000 - 500 = 500
    """
    _, biz = _create_user_and_business(db, "cmp@test.com", "Compare Biz")
    prod = _create_product(db, biz.business_id)
    # May sale
    _create_sale(db, biz.business_id, prod.product_id, 2000, 0, 1500, 50, 5.0, date(2026, 5, 15))
    # June sale
    _create_sale(db, biz.business_id, prod.product_id, 3000, 0, 2000, 80, 8.0, date(2026, 6, 15))
    db.commit()

    result = analytics_service.compare_months(
        db, biz.business_id,
        year_b=2026, month_b=6,
        year_a=2026, month_a=5,
    )
    assert result["period_b"]["gross_profit"] == 1000.0
    assert result["period_a"]["gross_profit"] == 500.0
    assert result["delta"]["gross_profit"] == 500.0


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

def _register_and_token(email: str) -> str:
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Test1234!!", "full_name": "Test"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_api_gross_profit_endpoint_returns_200():
    """API endpoint returns 200 for authenticated owner."""
    token = _register_and_token("api@test.com")
    biz_resp = client.post(
        "/api/businesses",
        json={"business_name": "API Test Biz"},
        headers=_auth(token),
    )
    biz_id = biz_resp.json()["business_id"]

    resp = client.get(
        f"/api/businesses/{biz_id}/analytics/gross-profit",
        params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "gross_profit" in body
    assert "gross_margin_pct" in body
    assert body["business_id"] == biz_id


def test_api_analytics_cross_tenant_returns_403():
    """User B cannot access User A's analytics."""
    token_a = _register_and_token("ana@test.com")
    token_b = _register_and_token("anb@test.com")

    biz_a = client.post(
        "/api/businesses", json={"business_name": "A Biz"}, headers=_auth(token_a)
    ).json()["business_id"]

    resp = client.get(
        f"/api/businesses/{biz_a}/analytics/revenue",
        params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
        headers=_auth(token_b),
    )
    assert resp.status_code == 403, (
        f"SECURITY VIOLATION: User B got {resp.status_code} on User A's analytics!"
    )


def test_api_analytics_unauthenticated_returns_403():
    """Analytics endpoints without a token return 403."""
    resp = client.get(
        "/api/businesses/1/analytics/revenue",
        params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
    )
    assert resp.status_code == 403
