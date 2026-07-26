"""
backend/app/services/analytics_service.py — Core Analytics Service
====================================================================
Implements deterministic financial metric calculations per
ANALYTICS_FORMULAS.md Section 1.

ALL functions:
    - Accept `business_id` as their first parameter.
    - Filter EVERY SQL query by `WHERE business_id = business_id`.
    - Never call external APIs or LLMs.
    - Return plain Python dicts (serialisable by FastAPI/Pydantic).

Formulas implemented (from ANALYTICS_FORMULAS.md Section 1):
    A. Gross Revenue     = SUM(selling_price)
    B. Net Revenue       = SUM(selling_price - discount)
    C. COGS              = SUM(cost_basis)
    D. Gross Profit      = Net Revenue - COGS
    E. Gross Margin %    = (Gross Profit / Net Revenue) * 100
    F. Making Charge/g   = SUM(making_charge) / SUM(weight)

Multi-tenancy rule (PROJECT_RULES.md Rule 11):
    A query that reads sales / purchases / products without filtering
    by business_id is a critical data-isolation bug. This is enforced
    by including `Sale.business_id == business_id` in every query here.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.sale import Sale


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _period_sales_query(db: Session, business_id: int, start_date: date, end_date: date):
    """
    Returns a SQLAlchemy query for Sale rows belonging to `business_id`
    within [start_date, end_date] (inclusive on both ends).
    """
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt   = datetime.combine(end_date,   datetime.max.time())
    return (
        db.query(Sale)
        .filter(
            Sale.business_id == business_id,        # MANDATORY: multi-tenant filter
            Sale.sale_date >= start_dt,
            Sale.sale_date <= end_dt,
        )
    )


def _safe_margin_pct(gross_profit: float, net_revenue: float) -> float | None:
    """
    Returns Gross Margin % or None if net_revenue is 0 (avoid division by zero).
    """
    if net_revenue == 0:
        return None
    return round((gross_profit / net_revenue) * 100, 4)


# ---------------------------------------------------------------------------
# Core metric functions
# ---------------------------------------------------------------------------

def calculate_revenue(
    db: Session,
    business_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """
    Formula A + B (ANALYTICS_FORMULAS.md §1):
        Gross Revenue = SUM(selling_price)
        Net Revenue   = SUM(selling_price - discount)

    Returns a dict with gross_revenue, total_discount, net_revenue,
    transaction_count, and the date range.
    """
    rows = (
        db.query(
            func.coalesce(func.sum(Sale.selling_price), 0).label("gross_revenue"),
            func.coalesce(func.sum(Sale.discount),       0).label("total_discount"),
            func.count(Sale.sale_id).label("transaction_count"),
        )
        .filter(
            Sale.business_id == business_id,
            Sale.sale_date >= datetime.combine(start_date, datetime.min.time()),
            Sale.sale_date <= datetime.combine(end_date,   datetime.max.time()),
        )
        .one()
    )

    gross_revenue      = float(rows.gross_revenue)
    total_discount     = float(rows.total_discount)
    net_revenue        = round(gross_revenue - total_discount, 2)

    return {
        "business_id":       business_id,
        "start_date":        start_date.isoformat(),
        "end_date":          end_date.isoformat(),
        "gross_revenue":     round(gross_revenue, 2),
        "total_discount":    round(total_discount, 2),
        "net_revenue":       net_revenue,
        "transaction_count": rows.transaction_count,
    }


def calculate_cogs(
    db: Session,
    business_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """
    Formula C (ANALYTICS_FORMULAS.md §1):
        COGS = SUM(cost_basis)

    For serialised items, cost_basis is the exact total_cost from the
    purchase record captured at billing time.
    """
    rows = (
        db.query(
            func.coalesce(func.sum(Sale.cost_basis), 0).label("cogs"),
            func.count(Sale.sale_id).label("transaction_count"),
        )
        .filter(
            Sale.business_id == business_id,
            Sale.sale_date >= datetime.combine(start_date, datetime.min.time()),
            Sale.sale_date <= datetime.combine(end_date,   datetime.max.time()),
        )
        .one()
    )

    return {
        "business_id":       business_id,
        "start_date":        start_date.isoformat(),
        "end_date":          end_date.isoformat(),
        "cogs":              round(float(rows.cogs), 2),
        "transaction_count": rows.transaction_count,
    }


def calculate_gross_profit(
    db: Session,
    business_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """
    Formulas C, D, E (ANALYTICS_FORMULAS.md §1):
        Gross Profit  = Net Revenue - COGS
                      = SUM(selling_price - discount - cost_basis)
        Gross Margin% = (Gross Profit / Net Revenue) * 100
    """
    rows = (
        db.query(
            func.coalesce(func.sum(Sale.selling_price), 0).label("gross_revenue"),
            func.coalesce(func.sum(Sale.discount),       0).label("total_discount"),
            func.coalesce(func.sum(Sale.cost_basis),     0).label("cogs"),
            func.coalesce(func.sum(Sale.making_charge),  0).label("total_making_charge"),
            func.coalesce(func.sum(Sale.weight),         0).label("total_weight"),
            func.count(Sale.sale_id).label("transaction_count"),
        )
        .filter(
            Sale.business_id == business_id,
            Sale.sale_date >= datetime.combine(start_date, datetime.min.time()),
            Sale.sale_date <= datetime.combine(end_date,   datetime.max.time()),
        )
        .one()
    )

    gross_revenue         = float(rows.gross_revenue)
    total_discount        = float(rows.total_discount)
    cogs                  = float(rows.cogs)
    total_making_charge   = float(rows.total_making_charge)
    total_weight          = float(rows.total_weight)

    net_revenue   = gross_revenue - total_discount
    gross_profit  = net_revenue - cogs
    margin_pct    = _safe_margin_pct(gross_profit, net_revenue)
    mc_per_gram   = round(total_making_charge / total_weight, 4) if total_weight > 0 else None

    return {
        "business_id":          business_id,
        "start_date":           start_date.isoformat(),
        "end_date":             end_date.isoformat(),
        "gross_revenue":        round(gross_revenue, 2),
        "total_discount":       round(total_discount, 2),
        "net_revenue":          round(net_revenue, 2),
        "cogs":                 round(cogs, 2),
        "gross_profit":         round(gross_profit, 2),
        "gross_margin_pct":     margin_pct,
        "total_making_charge":  round(total_making_charge, 2),
        "total_weight_grams":   round(total_weight, 4),
        "making_charge_per_gram": mc_per_gram,
        "transaction_count":    rows.transaction_count,
    }


def compare_months(
    db: Session,
    business_id: int,
    year_b: int,
    month_b: int,
    year_a: int,
    month_a: int,
) -> dict[str, Any]:
    """
    Compare Gross Profit between two calendar months (Month B vs Month A).

    Month A is the baseline; Month B is the target (typically the later month).
    Returns full metrics for both months plus the delta.
    """
    import calendar

    def _month_range(year: int, month: int) -> tuple[date, date]:
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    start_b, end_b = _month_range(year_b, month_b)
    start_a, end_a = _month_range(year_a, month_a)

    metrics_b = calculate_gross_profit(db, business_id, start_b, end_b)
    metrics_a = calculate_gross_profit(db, business_id, start_a, end_a)

    delta_gp          = round(metrics_b["gross_profit"]  - metrics_a["gross_profit"],  2)
    delta_net_revenue = round(metrics_b["net_revenue"]   - metrics_a["net_revenue"],   2)
    delta_cogs        = round(metrics_b["cogs"]          - metrics_a["cogs"],          2)

    return {
        "business_id": business_id,
        "period_b":    {"year": year_b, "month": month_b, **metrics_b},
        "period_a":    {"year": year_a, "month": month_a, **metrics_a},
        "delta": {
            "gross_profit":  delta_gp,
            "net_revenue":   delta_net_revenue,
            "cogs":          delta_cogs,
        },
    }
