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
