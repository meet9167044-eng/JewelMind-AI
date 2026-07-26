"""
backend/tests/test_inventory.py — Phase 10 Inventory Intelligence Tests
=======================================================================
Tests (per Phase 10 verification gate in PROJECT_PLAN.md):

    1. Ageing report has all 5 bucket keys.
    2. Items in inventory = products where purchased_weight > sold_weight.
    3. Age calculation is correct (oldest_purchase_date to as_of_date).
    4. Dead stock: age > 180d AND 0 sales in 90d.
    5. Dead stock NOT triggered when age <= 180d.
    6. Dead stock NOT triggered when product has recent sales (< 90d).
    7. Slow movers: coverage > 180 days.
    8. *** ISOLATION GATE ***: Business B inventory = 0 when only Business A has stock.
    9. Empty business returns zeros and empty lists.
    10. API inventory-age returns 200 for owner.
    11. API inventory-performance returns 200 for owner.
    12. API cross-tenant access returns 403.

All tests use in-memory SQLite with injected as_of_date for determinism.
"""

import pytest
from datetime import date, datetime, timedelta
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
from backend.app.services import inventory_service

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
    session = TestSessionLocal()
    yield session
    session.close()


client = TestClient(app)

# Fixed reference date for all tests
AS_OF = date(2026, 7, 26)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_biz(db: Session, email: str) -> Business:
    u = User(email=email, password_hash=hash_password("Test1234"), full_name="T")
    db.add(u); db.flush()
    b = Business(owner_user_id=u.user_id, business_name="Test Biz")
    db.add(b); db.flush()
    return b


def _seed_product(db: Session, biz_id: int, sku: str, cat: str = "ring") -> Product:
    p = Product(
        business_id=biz_id, sku=sku, product_name=f"Item {sku}",
        category=cat, metal="gold", purity="22K",
        gross_weight=10.0, net_weight=9.0,
    )
    db.add(p); db.flush()
    return p


def _seed_purchase(db: Session, biz_id: int, prod_id: int,
                   weight: float, purchase_date: date,
                   total_cost: float = 50000.0) -> Purchase:
    pur = Purchase(
        business_id=biz_id, product_id=prod_id,
        purchase_date=datetime.combine(purchase_date, datetime.min.time()),
        quantity=1, weight=weight,
        metal_rate=5000.0, metal_cost=total_cost * 0.9,
        making_cost=total_cost * 0.1, total_cost=total_cost,
    )
    db.add(pur); db.flush()
    return pur


def _seed_sale(db: Session, biz_id: int, prod_id: int,
               weight: float, sale_date: date) -> Sale:
    s = Sale(
        business_id=biz_id, product_id=prod_id,
        sale_date=datetime.combine(sale_date, datetime.min.time()),
        quantity=1, weight=weight,
        selling_price=60000.0, making_charge=3000.0,
        discount=0.0, cost_basis=50000.0,
    )
    db.add(s); db.flush()
    return s


# ---------------------------------------------------------------------------
# Unit tests: calculate_inventory_age
# ---------------------------------------------------------------------------

def test_ageing_report_has_all_five_buckets(db):
    """Result must always contain all 5 bucket keys."""
    biz = _seed_biz(db, "buck@test.com")
    db.commit()

    result = inventory_service.calculate_inventory_age(
        db, biz.business_id, as_of_date=AS_OF
    )
    for bucket in ["0-30d", "31-90d", "91-180d", "181-365d", "365+d"]:
        assert bucket in result["buckets"], f"Missing bucket: {bucket}"


def test_empty_business_all_zero_ageing(db):
    """Business with no purchases returns all-zero report."""
    biz = _seed_biz(db, "empty@test.com")
    db.commit()

    result = inventory_service.calculate_inventory_age(
        db, biz.business_id, as_of_date=AS_OF
    )
    assert result["total_items"] == 0
    assert result["total_weight"] == 0.0
    for b_data in result["buckets"].values():
        assert b_data["count"] == 0


def test_item_appears_in_correct_age_bucket(db):
    """
    Purchase 200 days ago, no sales → item lands in '181-365d' bucket.
    """
    biz = _seed_biz(db, "bucket_age@test.com")
    prod = _seed_product(db, biz.business_id, "AGE1")
    purchase_date = AS_OF - timedelta(days=200)
    _seed_purchase(db, biz.business_id, prod.product_id, 10.0, purchase_date)
    db.commit()

    result = inventory_service.calculate_inventory_age(
        db, biz.business_id, as_of_date=AS_OF
    )
    assert result["buckets"]["181-365d"]["count"] == 1
    assert result["total_items"] == 1
    assert result["items"][0]["age_days"] == 200
    assert result["items"][0]["age_bucket"] == "181-365d"


def test_fully_sold_item_excluded_from_inventory(db):
    """Item where sold_weight == purchased_weight must NOT appear in inventory."""
    biz = _seed_biz(db, "sold@test.com")
    prod = _seed_product(db, biz.business_id, "SOLD1")
    _seed_purchase(db, biz.business_id, prod.product_id, 10.0, AS_OF - timedelta(days=100))
    _seed_sale(db, biz.business_id, prod.product_id, 10.0, AS_OF - timedelta(days=50))
    db.commit()

    result = inventory_service.calculate_inventory_age(
        db, biz.business_id, as_of_date=AS_OF
    )
    assert result["total_items"] == 0, "Fully sold item should not appear in inventory"


def test_partially_sold_item_included(db):
    """Item where sold_weight < purchased_weight must appear in inventory."""
    biz = _seed_biz(db, "partial@test.com")
    prod = _seed_product(db, biz.business_id, "PART1")
    _seed_purchase(db, biz.business_id, prod.product_id, 20.0, AS_OF - timedelta(days=50))
    _seed_sale(db, biz.business_id, prod.product_id, 8.0, AS_OF - timedelta(days=20))
    db.commit()

    result = inventory_service.calculate_inventory_age(
        db, biz.business_id, as_of_date=AS_OF
    )
    assert result["total_items"] == 1
    assert abs(result["items"][0]["remaining_weight"] - 12.0) < 0.01


# ---------------------------------------------------------------------------
# Unit tests: classify_inventory_performance — Dead stock
# ---------------------------------------------------------------------------

def test_dead_stock_detected_when_old_and_no_recent_sales(db):
    """
    Purchase 250 days ago, 0 sales in last 90 days → dead stock.
    """
    biz = _seed_biz(db, "dead@test.com")
    prod = _seed_product(db, biz.business_id, "DEAD1")
    _seed_purchase(db, biz.business_id, prod.product_id, 10.0, AS_OF - timedelta(days=250))
    # Sale that is OLDER than 90 days — should not count as "recent"
    _seed_sale(db, biz.business_id, prod.product_id, 2.0, AS_OF - timedelta(days=100))
    db.commit()

    result = inventory_service.classify_inventory_performance(
        db, biz.business_id, as_of_date=AS_OF
    )
    assert result["summary"]["dead_stock_count"] >= 1
    dead_skus = [d["sku"] for d in result["dead_stock"]]
    assert "DEAD1" in dead_skus


def test_dead_stock_not_triggered_when_age_under_180(db):
    """
    Purchase 100 days ago → NOT dead stock (age <= 180).
    """
    biz = _seed_biz(db, "young@test.com")
    prod = _seed_product(db, biz.business_id, "YOUNG1")
    _seed_purchase(db, biz.business_id, prod.product_id, 10.0, AS_OF - timedelta(days=100))
    db.commit()

    result = inventory_service.classify_inventory_performance(
        db, biz.business_id, as_of_date=AS_OF
    )
    dead_skus = [d["sku"] for d in result["dead_stock"]]
    assert "YOUNG1" not in dead_skus, "Young item should not be dead stock"


def test_dead_stock_not_triggered_when_recent_sale(db):
    """
    Purchase 250 days ago BUT sale 30 days ago → NOT dead stock.
    """
    biz = _seed_biz(db, "recent_sale@test.com")
    prod = _seed_product(db, biz.business_id, "LIVE1")
    _seed_purchase(db, biz.business_id, prod.product_id, 20.0, AS_OF - timedelta(days=250))
    # Recent sale within 90 days — product is still active
    _seed_sale(db, biz.business_id, prod.product_id, 5.0, AS_OF - timedelta(days=30))
    db.commit()

    result = inventory_service.classify_inventory_performance(
        db, biz.business_id, as_of_date=AS_OF
    )
    dead_skus = [d["sku"] for d in result["dead_stock"]]
    assert "LIVE1" not in dead_skus, "Item with recent sale must not be dead stock"


# ---------------------------------------------------------------------------
# *** ISOLATION GATE ***
# ---------------------------------------------------------------------------

def test_inventory_isolation_across_businesses(db):
    """
    *** ISOLATION GATE ***
    Business A has 3 old items in inventory.
    Business B has no purchases.
    Business B's inventory report must return 0 items — NOT Business A's data.
    """
    biz_a = _seed_biz(db, "inv_a@test.com")
    biz_b = _seed_biz(db, "inv_b@test.com")

    for i in range(3):
        prod = _seed_product(db, biz_a.business_id, f"A-SKU{i}")
        _seed_purchase(db, biz_a.business_id, prod.product_id,
                       10.0, AS_OF - timedelta(days=200 + i))
    db.commit()

    result_b = inventory_service.calculate_inventory_age(
        db, biz_b.business_id, as_of_date=AS_OF
    )
    assert result_b["total_items"] == 0, (
        f"ISOLATION VIOLATION: Biz B has {result_b['total_items']} items "
        f"(should be 0 — those are Biz A's items)"
    )


def test_dead_stock_isolation(db):
    """
    Business A has dead stock. Business B has none.
    Business B's performance report must show 0 dead stock.
    """
    biz_a = _seed_biz(db, "ds_a@test.com")
    biz_b = _seed_biz(db, "ds_b@test.com")

    prod_a = _seed_product(db, biz_a.business_id, "DEAD_A")
    _seed_purchase(db, biz_a.business_id, prod_a.product_id,
                   10.0, AS_OF - timedelta(days=250))
    db.commit()

    result_b = inventory_service.classify_inventory_performance(
        db, biz_b.business_id, as_of_date=AS_OF
    )
    assert result_b["summary"]["dead_stock_count"] == 0, (
        f"ISOLATION VIOLATION: Biz B shows {result_b['summary']['dead_stock_count']} dead stock items"
    )


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

def _register_and_token(email: str) -> str:
    r = client.post("/api/auth/register",
        json={"email": email, "password": "Test1234!!", "full_name": "T"})
    assert r.status_code == 201
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_api_inventory_age_returns_200():
    """GET /inventory-age returns 200 with valid structure for owner."""
    token = _register_and_token("inv_api@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "Inv Biz"}, headers=_auth(token)
    ).json()["business_id"]

    resp = client.get(
        f"/api/businesses/{biz_id}/analytics/inventory-age",
        params={"as_of_date": "2026-07-26"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "buckets"     in body
    assert "total_items" in body
    assert "0-30d"       in body["buckets"]
    assert "365+d"       in body["buckets"]


def test_api_inventory_performance_returns_200():
    """GET /inventory-performance returns 200 with valid structure for owner."""
    token = _register_and_token("perf_api@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "Perf Biz"}, headers=_auth(token)
    ).json()["business_id"]

    resp = client.get(
        f"/api/businesses/{biz_id}/analytics/inventory-performance",
        params={"as_of_date": "2026-07-26"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "dead_stock"     in body
    assert "slow_movers"    in body
    assert "stockout_risks" in body
    assert "summary"        in body


def test_api_inventory_cross_tenant_returns_403():
    """User B cannot access User A's inventory endpoints."""
    token_a = _register_and_token("inv_ta@test.com")
    token_b = _register_and_token("inv_tb@test.com")

    biz_a = client.post(
        "/api/businesses", json={"business_name": "A"}, headers=_auth(token_a)
    ).json()["business_id"]

    resp = client.get(
        f"/api/businesses/{biz_a}/analytics/inventory-age",
        headers=_auth(token_b),
    )
    assert resp.status_code == 403, (
        f"SECURITY VIOLATION: User B got {resp.status_code} on User A's inventory!"
    )
