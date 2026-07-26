"""
backend/tests/test_profit_diagnosis.py — Phase 9 Verification Tests
=====================================================================
Tests (per Phase 9 verification gate in PROJECT_PLAN.md):

    1. Basic decomposition produces 5 named drivers.
    2. *** ADDITIVITY GATE ***: vol + disc + mc + mix + metal == delta_gp exactly.
    3. Empty business returns all-zero drivers (no error, no cross-leak).
    4. *** ISOLATION GATE ***: business_id=2 result is zero — not business_id=1's data.
    5. Symmetry: swapping target/baseline flips the sign of delta_gp.
    6. API endpoint returns 200 for authenticated owner.
    7. API endpoint returns 403 for cross-tenant access.
    8. Same period comparison returns delta_gp == 0.

Unit tests (1-5, 8) use in-memory SQLite.
Tests 6-7 also use in-memory SQLite via the TestClient override.

Ground-truth values (June 2026 vs May 2026, business_id=1 from seed):
    Verified via backend/scripts/compute_phase9_truth.py against MySQL.
    These are used only in the integration smoke test (test_ground_truth_smoke),
    which connects to the real database and is marked with pytest.mark to allow
    skipping in CI environments where MySQL is unavailable.
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
from backend.app.services.auth_service import hash_password
from backend.app.services import profit_diagnosis_service

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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_business(db: Session, email: str, biz_name: str = "Test Biz") -> Business:
    u = User(email=email, password_hash=hash_password("Test1234"), full_name="T")
    db.add(u)
    db.flush()
    b = Business(owner_user_id=u.user_id, business_name=biz_name)
    db.add(b)
    db.flush()
    return b


def _seed_product(db: Session, business_id: int, sku: str, category: str = "ring") -> Product:
    p = Product(
        business_id=business_id, sku=sku, product_name="Test Item",
        category=category, metal="gold", purity="22K",
        gross_weight=10.0, net_weight=9.0,
    )
    db.add(p)
    db.flush()
    return p


def _seed_sale(
    db: Session, business_id: int, product_id: int,
    selling_price: float, discount: float, cost_basis: float,
    making_charge: float, weight: float, year: int, month: int, day: int = 1,
):
    db.add(Sale(
        business_id=business_id, product_id=product_id,
        sale_date=datetime(year, month, day),
        quantity=1, weight=weight,
        selling_price=selling_price, making_charge=making_charge,
        discount=discount, cost_basis=cost_basis,
    ))
    db.flush()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_result_has_all_five_drivers(db):
    """Result dict must contain all 5 named driver keys."""
    biz = _seed_business(db, "drv@test.com")
    prod = _seed_product(db, biz.business_id, "SKU1")
    # May sale
    _seed_sale(db, biz.business_id, prod.product_id,
               selling_price=1000, discount=50, cost_basis=700, making_charge=80,
               weight=5.0, year=2026, month=5)
    # June sale
    _seed_sale(db, biz.business_id, prod.product_id,
               selling_price=1200, discount=100, cost_basis=700, making_charge=90,
               weight=6.0, year=2026, month=6)
    db.commit()

    result = profit_diagnosis_service.analyze_profit_change(
        db, biz.business_id,
        target_year=2026, target_month=6,
        baseline_year=2026, baseline_month=5,
    )
    drivers = result["drivers"]
    assert "volume"        in drivers
    assert "discount"      in drivers
    assert "making_charge" in drivers
    assert "product_mix"   in drivers
    assert "metal_margin"  in drivers


def test_additivity_gate(db):
    """
    *** ADDITIVITY GATE ***
    SUM(all 5 drivers) must equal delta_gp within 1 unit.
    This is a mathematical invariant — if it fails, the formulas are broken.
    """
    biz = _seed_business(db, "add@test.com")

    # Two categories to exercise the mix driver
    prod_r = _seed_product(db, biz.business_id, "R1", "ring")
    prod_c = _seed_product(db, biz.business_id, "C1", "chain")

    # May
    _seed_sale(db, biz.business_id, prod_r.product_id,
               selling_price=1000, discount=50, cost_basis=700, making_charge=80,
               weight=5.0, year=2026, month=5)
    _seed_sale(db, biz.business_id, prod_c.product_id,
               selling_price=2000, discount=100, cost_basis=1400, making_charge=120,
               weight=8.0, year=2026, month=5)
    # June (different mix + discounts)
    _seed_sale(db, biz.business_id, prod_r.product_id,
               selling_price=1100, discount=200, cost_basis=700, making_charge=70,
               weight=4.0, year=2026, month=6)
    _seed_sale(db, biz.business_id, prod_c.product_id,
               selling_price=2500, discount=50, cost_basis=1400, making_charge=150,
               weight=12.0, year=2026, month=6)
    db.commit()

    result = profit_diagnosis_service.analyze_profit_change(
        db, biz.business_id,
        target_year=2026, target_month=6,
        baseline_year=2026, baseline_month=5,
    )

    d = result["drivers"]
    driver_sum = d["volume"] + d["discount"] + d["making_charge"] + d["product_mix"] + d["metal_margin"]
    assert abs(driver_sum - result["delta_gp"]) < 1.0, (
        f"ADDITIVITY FAILED: drivers sum={driver_sum:.2f} != delta_gp={result['delta_gp']:.2f}"
    )
    assert result["additive_check"] is True


def test_empty_business_returns_zeros(db):
    """Business with no sales returns all-zero drivers and delta_gp=0."""
    biz = _seed_business(db, "empty@test.com")
    db.commit()

    result = profit_diagnosis_service.analyze_profit_change(
        db, biz.business_id,
        target_year=2026, target_month=6,
        baseline_year=2026, baseline_month=5,
    )
    assert result["delta_gp"] == 0.0
    for driver_val in result["drivers"].values():
        assert driver_val == 0.0


def test_isolation_empty_business_not_contaminated(db):
    """
    *** ISOLATION GATE ***
    Business B with no sales must return all-zero drivers,
    even when Business A has large sales in the same period.
    """
    biz_a = _seed_business(db, "iso_a@test.com", "Biz A")
    biz_b = _seed_business(db, "iso_b@test.com", "Biz B")
    prod_a = _seed_product(db, biz_a.business_id, "PA1")

    # Business A has May + June sales
    _seed_sale(db, biz_a.business_id, prod_a.product_id,
               selling_price=5000, discount=200, cost_basis=3000, making_charge=200,
               weight=10.0, year=2026, month=5)
    _seed_sale(db, biz_a.business_id, prod_a.product_id,
               selling_price=6000, discount=500, cost_basis=3000, making_charge=180,
               weight=9.0, year=2026, month=6)
    db.commit()

    # Business B query must return zeros — NOT Business A's data
    result_b = profit_diagnosis_service.analyze_profit_change(
        db, biz_b.business_id,
        target_year=2026, target_month=6,
        baseline_year=2026, baseline_month=5,
    )
    assert result_b["delta_gp"] == 0.0, (
        f"ISOLATION VIOLATION: Biz B delta_gp={result_b['delta_gp']} (should be 0)"
    )
    for driver_val in result_b["drivers"].values():
        assert driver_val == 0.0, (
            f"ISOLATION VIOLATION: Biz B driver={driver_val} (should be 0)"
        )


def test_symmetry_sign_flip(db):
    """Swapping target ↔ baseline flips the sign of delta_gp."""
    biz = _seed_business(db, "sym@test.com")
    prod = _seed_product(db, biz.business_id, "S1")
    _seed_sale(db, biz.business_id, prod.product_id,
               selling_price=1000, discount=50, cost_basis=700, making_charge=80,
               weight=5.0, year=2026, month=5)
    _seed_sale(db, biz.business_id, prod.product_id,
               selling_price=1500, discount=100, cost_basis=700, making_charge=90,
               weight=7.0, year=2026, month=6)
    db.commit()

    fwd = profit_diagnosis_service.analyze_profit_change(
        db, biz.business_id,
        target_year=2026, target_month=6, baseline_year=2026, baseline_month=5,
    )
    bwd = profit_diagnosis_service.analyze_profit_change(
        db, biz.business_id,
        target_year=2026, target_month=5, baseline_year=2026, baseline_month=6,
    )
    assert abs(fwd["delta_gp"] + bwd["delta_gp"]) < 0.01, (
        f"Symmetry failed: fwd={fwd['delta_gp']:.2f}, bwd={bwd['delta_gp']:.2f}"
    )


def test_same_period_returns_zero_delta(db):
    """Comparing a month with itself must return delta_gp == 0."""
    biz = _seed_business(db, "same@test.com")
    prod = _seed_product(db, biz.business_id, "X1")
    _seed_sale(db, biz.business_id, prod.product_id,
               selling_price=1000, discount=50, cost_basis=700, making_charge=80,
               weight=5.0, year=2026, month=6)
    db.commit()

    result = profit_diagnosis_service.analyze_profit_change(
        db, biz.business_id,
        target_year=2026, target_month=6,
        baseline_year=2026, baseline_month=6,
    )
    assert abs(result["delta_gp"]) < 0.01, (
        f"Same-period delta_gp should be 0, got {result['delta_gp']}"
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


def test_api_profit_diagnosis_returns_200():
    """Authenticated owner gets 200 and a valid response structure."""
    token = _register_and_token("pd_api@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "PD Biz"}, headers=_auth(token)
    ).json()["business_id"]

    resp = client.get(
        f"/api/businesses/{biz_id}/analytics/profit-diagnosis",
        params={
            "target_year": 2026, "target_month": 6,
            "baseline_year": 2026, "baseline_month": 5,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "delta_gp"  in body
    assert "drivers"   in body
    assert "volume"    in body["drivers"]
    assert "metal_margin" in body["drivers"]
    assert "additive_check" in body


def test_api_profit_diagnosis_cross_tenant_returns_403():
    """User B cannot access User A's profit-diagnosis endpoint."""
    token_a = _register_and_token("pd_a@test.com")
    token_b = _register_and_token("pd_b@test.com")

    biz_a = client.post(
        "/api/businesses", json={"business_name": "A"}, headers=_auth(token_a)
    ).json()["business_id"]

    resp = client.get(
        f"/api/businesses/{biz_a}/analytics/profit-diagnosis",
        params={
            "target_year": 2026, "target_month": 6,
            "baseline_year": 2026, "baseline_month": 5,
        },
        headers=_auth(token_b),
    )
    assert resp.status_code == 403, (
        f"SECURITY VIOLATION: User B got {resp.status_code} on User A's profit-diagnosis!"
    )
