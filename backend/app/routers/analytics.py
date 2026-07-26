"""
backend/app/routers/analytics.py — Core Analytics Endpoints
============================================================
All routes are scoped under /api/businesses/{business_id}/analytics/

ALL routes use the `get_owned_business` dependency from Phase 6.
This guarantees:
    1. The requester is authenticated (valid JWT).
    2. The requester owns the requested business_id.
    3. business.business_id is safe to pass to analytics functions.

No LLMs, no external APIs — pure deterministic calculation.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.business import get_owned_business
from backend.app.models.business import Business
from backend.app.services import analytics_service
from backend.app.services import profit_diagnosis_service

router = APIRouter(
    prefix="/api/businesses/{business_id}/analytics",
    tags=["Analytics"],
)


# ── Revenue ───────────────────────────────────────────────────────────────────

@router.get(
    "/revenue",
    summary="Gross and Net Revenue for a date range",
)
def get_revenue(
    start_date: date = Query(..., description="Start date (inclusive). Format: YYYY-MM-DD"),
    end_date:   date = Query(..., description="End date (inclusive).   Format: YYYY-MM-DD"),
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Returns Gross Revenue, Total Discount, and Net Revenue for the given
    date range, scoped to the authenticated user's business.

    Formula (ANALYTICS_FORMULAS.md §1.A–B):
    - **Gross Revenue** = SUM(selling_price)
    - **Net Revenue**   = SUM(selling_price - discount)
    """
    return analytics_service.calculate_revenue(
        db, business.business_id, start_date, end_date
    )


# ── COGS ──────────────────────────────────────────────────────────────────────

@router.get(
    "/cogs",
    summary="Cost of Goods Sold for a date range",
)
def get_cogs(
    start_date: date = Query(..., description="Start date (inclusive). Format: YYYY-MM-DD"),
    end_date:   date = Query(..., description="End date (inclusive).   Format: YYYY-MM-DD"),
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Returns COGS (Cost of Goods Sold) for the given date range.

    Formula (ANALYTICS_FORMULAS.md §1.C):
    - **COGS** = SUM(cost_basis)
    """
    return analytics_service.calculate_cogs(
        db, business.business_id, start_date, end_date
    )


# ── Gross Profit ──────────────────────────────────────────────────────────────

@router.get(
    "/gross-profit",
    summary="Full P&L summary: Revenue, COGS, Gross Profit, Margin",
)
def get_gross_profit(
    start_date: date = Query(..., description="Start date (inclusive). Format: YYYY-MM-DD"),
    end_date:   date = Query(..., description="End date (inclusive).   Format: YYYY-MM-DD"),
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Returns a full P&L summary for the given date range.

    Formulas (ANALYTICS_FORMULAS.md §1.D–F):
    - **Gross Profit**     = Net Revenue - COGS
    - **Gross Margin %**   = (Gross Profit / Net Revenue) × 100
    - **Making Charge/g**  = SUM(making_charge) / SUM(weight)
    """
    return analytics_service.calculate_gross_profit(
        db, business.business_id, start_date, end_date
    )


# ── Month Comparison ──────────────────────────────────────────────────────────

@router.get(
    "/compare-months",
    summary="Compare Gross Profit between two calendar months",
)
def compare_months(
    year_b:  int = Query(..., description="Target month year  (e.g. 2026)", ge=2000, le=2100),
    month_b: int = Query(..., description="Target month number (1-12)",      ge=1,    le=12),
    year_a:  int = Query(..., description="Baseline month year (e.g. 2026)", ge=2000, le=2100),
    month_a: int = Query(..., description="Baseline month number (1-12)",    ge=1,    le=12),
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Compares Gross Profit between two calendar months (B vs A).

    - **period_b**: target month (typically the more recent one, e.g. June)
    - **period_a**: baseline month (e.g. May)
    - **delta.gross_profit**: positive = improvement, negative = decline
    """
    return analytics_service.compare_months(
        db,
        business.business_id,
        year_b=year_b, month_b=month_b,
        year_a=year_a, month_a=month_a,
    )


# ── Profit Diagnosis ──────────────────────────────────────────────────────────

@router.get(
    "/profit-diagnosis",
    summary="Variance decomposition: explain GP change between two months",
)
def profit_diagnosis(
    target_year:    int = Query(..., description="Target month year (e.g. 2026)",  ge=2000, le=2100),
    target_month:   int = Query(..., description="Target month number (1-12)",      ge=1,    le=12),
    baseline_year:  int = Query(..., description="Baseline month year (e.g. 2026)", ge=2000, le=2100),
    baseline_month: int = Query(..., description="Baseline month number (1-12)",    ge=1,    le=12),
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Decomposes total Gross Profit change between two months into
    **5 additive independent drivers** (ANALYTICS_FORMULAS.md Section 2):

    - **volume**        — impact of selling more/less total weight
    - **discount**      — impact of change in discount rate per gram
    - **making_charge** — impact of change in making-charge rate per gram
    - **product_mix**   — impact of shift in category weight proportions
    - **metal_margin**  — residual (metal acquisition cost fluctuations)

    All five drivers sum exactly to `delta_gp`.
    """
    return profit_diagnosis_service.analyze_profit_change(
        db,
        business_id=business.business_id,
        target_year=target_year,
        target_month=target_month,
        baseline_year=baseline_year,
        baseline_month=baseline_month,
    )


# ── Inventory Intelligence ────────────────────────────────────────────────────

from backend.app.services import inventory_service  # noqa: E402


@router.get(
    "/inventory-age",
    summary="Inventory ageing report: groups unsold stock into 5 ageing buckets",
)
def get_inventory_age(
    as_of_date: date | None = Query(None, description="Reference date (default: today). Format: YYYY-MM-DD"),
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Returns unsold inventory grouped into ageing buckets per
    ANALYTICS_FORMULAS.md §3.A:

    - **0-30d** / **31-90d** / **91-180d** / **181-365d** / **365+d**

    Each bucket shows item count, total weight (g), and total value (cost).
    A per-item detail list is also returned, sorted by age descending.
    """
    return inventory_service.calculate_inventory_age(
        db, business.business_id, as_of_date=as_of_date
    )


@router.get(
    "/inventory-performance",
    summary="Inventory classification: dead stock, slow movers, stockout risks",
)
def get_inventory_performance(
    as_of_date: date | None = Query(None, description="Reference date (default: today). Format: YYYY-MM-DD"),
    coverage_lookback_days: int = Query(30, description="Lookback window for avg daily sales (default: 30)", ge=7, le=180),
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Classifies active inventory per ANALYTICS_FORMULAS.md §3.C:

    - **dead_stock**      — age > 180 days AND 0 sales in last 90 days
    - **slow_movers**     — stock coverage > 180 days
    - **stockout_risks**  — fast mover AND coverage < 15 days

    Also returns per-category stock coverage in days.
    """
    return inventory_service.classify_inventory_performance(
        db, business.business_id,
        as_of_date=as_of_date,
        coverage_lookback_days=coverage_lookback_days,
    )
