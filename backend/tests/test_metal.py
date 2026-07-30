"""
backend/tests/test_metal.py — Phase 11 Metal Exposure & Scenario Tests
=======================================================================
Tests (per Phase 11 verification gate in PROJECT_PLAN.md):

    1.  WAR formula: SUM(metal_cost)/SUM(net_weight) is exact.
    2.  Valuation exposure is positive when market rate > WAR.
    3.  Valuation exposure is negative when market rate < WAR.
    4.  Empty inventory returns zero exposure.
    5.  *** ISOLATION GATE ***: Biz B exposure = 0 even when Biz A has inventory.
    6.  Scenario simulation: positive shift increases exposure.
    7.  Scenario simulation: negative shift decreases exposure.
    8.  Delta value = simulated_exposure - current_exposure (additive check).
    9.  0% shift → delta_value == 0.
    10. Metal rate fetch fail-safe: fetch_and_store_today returns False on network
        error — does NOT raise, does NOT crash the app.
    11. fetch_and_store_today persists rates when provider succeeds (mock provider).
    12. API /rates returns 200 with correct structure.
    13. API /exposure/gold returns 200 for owner.
    14. API /exposure/silver returns 200 for owner.
    15. API /simulate/gold returns 200 with delta_value for owner.
    16. API cross-tenant returns 403.

Tests use in-memory SQLite + rate rows seeded directly into MetalRate model.
No real external API calls are made in any test.
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch

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
from backend.app.models.metal_rate import MetalRate
from backend.app.services.auth_service import hash_password
from backend.app.services import metal_service
from backend.app.services.metal_rate_fetcher import (
    FetchedRates, fetch_and_store_today, AbstractMetalRateProvider,
)

# ---------------------------------------------------------------------------
# In-memory SQLite setup
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
    s = TestSessionLocal()
    yield s
    s.close()


client = TestClient(app)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_rate(db: Session, gold_24k: float, gold_22k: float, silver: float,
               rate_date: date = date(2026, 7, 26)) -> MetalRate:
    r = MetalRate(rate_date=rate_date, gold_24k=gold_24k, gold_22k=gold_22k, silver=silver)
    db.add(r); db.commit()
    return r


def _seed_biz(db: Session, email: str) -> Business:
    u = User(email=email, password_hash=hash_password("Test1234"), full_name="T")
    db.add(u); db.flush()
    b = Business(owner_user_id=u.user_id, business_name="Biz")
    db.add(b); db.flush()
    return b


def _seed_product(db: Session, biz_id: int, sku: str,
                  metal: str = "gold", purity: str = "22K",
                  net_weight: float = 10.0) -> Product:
    p = Product(
        business_id=biz_id, sku=sku, product_name=f"Item {sku}",
        category="ring", metal=metal, purity=purity,
        gross_weight=net_weight * 1.05, net_weight=net_weight,
    )
    db.add(p); db.flush()
    return p


def _seed_purchase(db: Session, biz_id: int, prod_id: int,
                   weight: float, metal_cost: float, total_cost: float) -> Purchase:
    pur = Purchase(
        business_id=biz_id, product_id=prod_id,
        purchase_date=date(2026, 5, 1),
        quantity=1, weight=weight,
        metal_rate=metal_cost / weight,
        metal_cost=metal_cost,
        making_cost=total_cost - metal_cost,
        total_cost=total_cost,
    )
    db.add(pur); db.flush()
    return pur


def _seed_sale(db: Session, biz_id: int, prod_id: int, weight: float) -> Sale:
    db.add(Sale(
        business_id=biz_id, product_id=prod_id,
        sale_date=date(2026, 6, 1),
        quantity=1, weight=weight,
        selling_price=70000.0, making_charge=3000.0,
        discount=0.0, cost_basis=55000.0,
    ))
    db.flush()


# ---------------------------------------------------------------------------
# Unit tests: WAR and Valuation Exposure
# ---------------------------------------------------------------------------

def test_war_formula_exact(db):
    """WAR = SUM(metal_cost) / SUM(net_weight) — exact formula check."""
    _seed_rate(db, gold_24k=7200.0, gold_22k=6600.0, silver=85.0)
    biz  = _seed_biz(db, "war@test.com")
    prod = _seed_product(db, biz.business_id, "G1", net_weight=10.0)
    _seed_purchase(db, biz.business_id, prod.product_id,
                   weight=10.0, metal_cost=60000.0, total_cost=65000.0)
    db.commit()

    result = metal_service.calculate_metal_exposure(db, biz.business_id, "gold")
    expected_war = 60000.0 / 10.0  # = 6000.0
    assert abs(result["war"] - expected_war) < 0.01, (
        f"WAR mismatch: got {result['war']}, expected {expected_war}"
    )


def test_valuation_exposure_positive_when_market_above_war(db):
    """
    When market rate > WAR, exposure is positive
    (inventory worth more than acquisition cost).
    """
    # gold_22k rate = 6600/g, WAR = 6000/g → positive exposure
    _seed_rate(db, gold_24k=7200.0, gold_22k=6600.0, silver=85.0)
    biz  = _seed_biz(db, "pos@test.com")
    prod = _seed_product(db, biz.business_id, "POS1", purity="22K", net_weight=10.0)
    _seed_purchase(db, biz.business_id, prod.product_id,
                   weight=10.0, metal_cost=60000.0, total_cost=65000.0)
    db.commit()

    result = metal_service.calculate_metal_exposure(db, biz.business_id, "gold")
    assert result["valuation_exposure"] > 0, (
        f"Expected positive exposure, got {result['valuation_exposure']}"
    )


def test_valuation_exposure_negative_when_market_below_war(db):
    """
    When market rate < WAR, exposure is negative
    (inventory worth less than acquisition cost).
    """
    # gold_22k rate = 5500/g, WAR = 6500/g → negative exposure
    _seed_rate(db, gold_24k=6000.0, gold_22k=5500.0, silver=85.0)
    biz  = _seed_biz(db, "neg@test.com")
    prod = _seed_product(db, biz.business_id, "NEG1", purity="22K", net_weight=10.0)
    _seed_purchase(db, biz.business_id, prod.product_id,
                   weight=10.0, metal_cost=65000.0, total_cost=70000.0)
    db.commit()

    result = metal_service.calculate_metal_exposure(db, biz.business_id, "gold")
    assert result["valuation_exposure"] < 0, (
        f"Expected negative exposure, got {result['valuation_exposure']}"
    )


def test_empty_inventory_returns_zero_exposure(db):
    """Business with no active gold inventory returns zero exposure."""
    _seed_rate(db, gold_24k=7200.0, gold_22k=6600.0, silver=85.0)
    biz = _seed_biz(db, "empty@test.com")
    db.commit()

    result = metal_service.calculate_metal_exposure(db, biz.business_id, "gold")
    assert result["valuation_exposure"] == 0.0
    assert result["item_count"] == 0


def test_fully_sold_item_excluded_from_exposure(db):
    """Item where sold_weight == purchased_weight must NOT count in exposure."""
    _seed_rate(db, gold_24k=7200.0, gold_22k=6600.0, silver=85.0)
    biz  = _seed_biz(db, "sold@test.com")
    prod = _seed_product(db, biz.business_id, "SOLD1", net_weight=10.0)
    _seed_purchase(db, biz.business_id, prod.product_id,
                   weight=10.0, metal_cost=60000.0, total_cost=65000.0)
    _seed_sale(db, biz.business_id, prod.product_id, weight=10.0)
    db.commit()

    result = metal_service.calculate_metal_exposure(db, biz.business_id, "gold")
    assert result["item_count"] == 0
    assert result["valuation_exposure"] == 0.0


# ---------------------------------------------------------------------------
# *** ISOLATION GATE ***
# ---------------------------------------------------------------------------

def test_metal_isolation_across_businesses(db):
    """
    *** ISOLATION GATE ***
    Business A has gold inventory. Business B has none.
    Business B's exposure must be 0 — NOT Business A's data.
    """
    _seed_rate(db, gold_24k=7200.0, gold_22k=6600.0, silver=85.0)
    biz_a = _seed_biz(db, "iso_a@test.com")
    biz_b = _seed_biz(db, "iso_b@test.com")

    prod_a = _seed_product(db, biz_a.business_id, "A_GOLD")
    _seed_purchase(db, biz_a.business_id, prod_a.product_id,
                   weight=20.0, metal_cost=130000.0, total_cost=140000.0)
    db.commit()

    result_b = metal_service.calculate_metal_exposure(db, biz_b.business_id, "gold")
    assert result_b["valuation_exposure"] == 0.0, (
        f"ISOLATION VIOLATION: Biz B exposure = {result_b['valuation_exposure']} "
        f"(should be 0 — that's Biz A's inventory)"
    )
    assert result_b["item_count"] == 0


# ---------------------------------------------------------------------------
# Unit tests: Scenario Simulation
# ---------------------------------------------------------------------------

def test_simulation_positive_shift_increases_exposure(db):
    """A +10% price rise should increase valuation exposure."""
    _seed_rate(db, gold_24k=7200.0, gold_22k=6600.0, silver=85.0)
    biz  = _seed_biz(db, "sim_up@test.com")
    prod = _seed_product(db, biz.business_id, "SIM1", net_weight=10.0)
    _seed_purchase(db, biz.business_id, prod.product_id,
                   weight=10.0, metal_cost=60000.0, total_cost=65000.0)
    db.commit()

    result = metal_service.simulate_metal_rate_shift(
        db, biz.business_id, "gold", change_percent=10.0
    )
    assert result["simulated_exposure"] > result["current_exposure"], (
        "10% price rise should increase simulated exposure"
    )
    assert result["delta_value"] > 0


def test_simulation_negative_shift_decreases_exposure(db):
    """A -10% price drop should decrease valuation exposure."""
    _seed_rate(db, gold_24k=7200.0, gold_22k=6600.0, silver=85.0)
    biz  = _seed_biz(db, "sim_dn@test.com")
    prod = _seed_product(db, biz.business_id, "SIM2", net_weight=10.0)
    _seed_purchase(db, biz.business_id, prod.product_id,
                   weight=10.0, metal_cost=60000.0, total_cost=65000.0)
    db.commit()

    result = metal_service.simulate_metal_rate_shift(
        db, biz.business_id, "gold", change_percent=-10.0
    )
    assert result["simulated_exposure"] < result["current_exposure"], (
        "10% price drop should decrease simulated exposure"
    )
    assert result["delta_value"] < 0


def test_simulation_additive_check(db):
    """delta_value == simulated_exposure - current_exposure (mathematical invariant)."""
    _seed_rate(db, gold_24k=7200.0, gold_22k=6600.0, silver=85.0)
    biz  = _seed_biz(db, "add@test.com")
    prod = _seed_product(db, biz.business_id, "ADD1", net_weight=15.0)
    _seed_purchase(db, biz.business_id, prod.product_id,
                   weight=15.0, metal_cost=90000.0, total_cost=97000.0)
    db.commit()

    result = metal_service.simulate_metal_rate_shift(
        db, biz.business_id, "gold", change_percent=-5.0
    )
    expected_delta = result["simulated_exposure"] - result["current_exposure"]
    assert abs(result["delta_value"] - expected_delta) < 0.01, (
        f"ADDITIVE FAIL: delta_value={result['delta_value']:.2f}, "
        f"expected={expected_delta:.2f}"
    )


def test_simulation_zero_shift_gives_zero_delta(db):
    """0% shift → delta_value == 0 (no change)."""
    _seed_rate(db, gold_24k=7200.0, gold_22k=6600.0, silver=85.0)
    biz  = _seed_biz(db, "zero@test.com")
    prod = _seed_product(db, biz.business_id, "ZERO1", net_weight=10.0)
    _seed_purchase(db, biz.business_id, prod.product_id,
                   weight=10.0, metal_cost=60000.0, total_cost=65000.0)
    db.commit()

    result = metal_service.simulate_metal_rate_shift(
        db, biz.business_id, "gold", change_percent=0.0
    )
    assert abs(result["delta_value"]) < 0.01, (
        f"0% shift should give delta=0, got {result['delta_value']}"
    )


# ---------------------------------------------------------------------------
# Fail-safe tests (metal_rate_fetcher)
# ---------------------------------------------------------------------------

class _FailingProvider(AbstractMetalRateProvider):
    """Always raises a network error — simulates offline API."""
    def fetch_today(self) -> FetchedRates:
        raise ConnectionError("Simulated network timeout")


class _SuccessProvider(AbstractMetalRateProvider):
    """Always returns fixed synthetic rates."""
    def fetch_today(self) -> FetchedRates:
        return FetchedRates(
            rate_date=date(2026, 7, 26),
            gold_24k=7200.0, gold_22k=6600.0, silver=85.0,
        )


def test_fetch_fail_safe_returns_false_does_not_raise():
    """
    *** FAIL-SAFE GATE ***
    When the external provider raises, fetch_and_store_today must:
      - Return False (not raise)
      - NOT crash the application
    (Rule 22: fail-safe fallback)
    """
    with patch(
        "backend.app.services.metal_rate_fetcher.get_provider",
        return_value=_FailingProvider(),
    ):
        result = fetch_and_store_today(TestSessionLocal)

    assert result is False, (
        "fetch_and_store_today must return False when the provider fails"
    )


def test_fetch_success_persists_to_db():
    """
    When the provider succeeds, fetch_and_store_today must:
      - Return True
      - Persist the rates to the metal_rates table
    """
    # Set up a fresh DB session for this test
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    LocalSession = sessionmaker(bind=engine)

    with patch(
        "backend.app.services.metal_rate_fetcher.get_provider",
        return_value=_SuccessProvider(),
    ):
        result = fetch_and_store_today(LocalSession)

    assert result is True

    # Verify rates were stored
    db = LocalSession()
    stored = db.query(MetalRate).first()
    db.close()
    assert stored is not None
    assert abs(float(stored.gold_24k) - 7200.0) < 0.01
    assert abs(float(stored.silver) - 85.0) < 0.01

    Base.metadata.drop_all(bind=engine)


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


def test_api_metal_rates_returns_200():
    """GET /metal/rates returns 200 with valid structure."""
    token = _register_and_token("rates_api@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "Metal Biz"}, headers=_auth(token)
    ).json()["business_id"]

    # Seed a rate row via the DB
    db = TestSessionLocal()
    db.add(MetalRate(rate_date=date(2026, 7, 26),
                     gold_24k=7200.0, gold_22k=6600.0, silver=85.0))
    db.commit(); db.close()

    resp = client.get(
        f"/api/businesses/{biz_id}/analytics/metal/rates",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "available" in body


def test_api_metal_exposure_gold_returns_200():
    """GET /metal/exposure/gold returns 200 for owner."""
    token = _register_and_token("exp_g@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "Gold Biz"}, headers=_auth(token)
    ).json()["business_id"]

    db = TestSessionLocal()
    db.add(MetalRate(rate_date=date(2026, 7, 26),
                     gold_24k=7200.0, gold_22k=6600.0, silver=85.0))
    db.commit(); db.close()

    resp = client.get(
        f"/api/businesses/{biz_id}/analytics/metal/exposure/gold",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "valuation_exposure" in body
    assert "war"                in body


def test_api_metal_exposure_silver_returns_200():
    """GET /metal/exposure/silver returns 200 for owner."""
    token = _register_and_token("exp_s@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "Silver Biz"}, headers=_auth(token)
    ).json()["business_id"]

    db = TestSessionLocal()
    db.add(MetalRate(rate_date=date(2026, 7, 26),
                     gold_24k=7200.0, gold_22k=6600.0, silver=85.0))
    db.commit(); db.close()

    resp = client.get(
        f"/api/businesses/{biz_id}/analytics/metal/exposure/silver",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text


def test_api_simulate_returns_200_with_delta():
    """GET /metal/simulate/gold returns 200 with delta_value."""
    token = _register_and_token("sim_api@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "Sim Biz"}, headers=_auth(token)
    ).json()["business_id"]

    db = TestSessionLocal()
    db.add(MetalRate(rate_date=date(2026, 7, 26),
                     gold_24k=7200.0, gold_22k=6600.0, silver=85.0))
    db.commit(); db.close()

    resp = client.get(
        f"/api/businesses/{biz_id}/analytics/metal/simulate/gold",
        params={"change_percent": -10.0},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "delta_value"        in body
    assert "simulated_exposure" in body
    assert "current_exposure"   in body


def test_api_metal_cross_tenant_returns_403():
    """User B cannot access User A's metal exposure endpoint."""
    token_a = _register_and_token("met_a@test.com")
    token_b = _register_and_token("met_b@test.com")

    biz_a = client.post(
        "/api/businesses", json={"business_name": "A"}, headers=_auth(token_a)
    ).json()["business_id"]

    db = TestSessionLocal()
    db.add(MetalRate(rate_date=date(2026, 7, 26),
                     gold_24k=7200.0, gold_22k=6600.0, silver=85.0))
    db.commit(); db.close()

    resp = client.get(
        f"/api/businesses/{biz_a}/analytics/metal/exposure/gold",
        headers=_auth(token_b),
    )
    assert resp.status_code == 403, (
        f"SECURITY VIOLATION: User B got {resp.status_code} on User A's metal data!"
    )
