"""
backend/app/services/profit_diagnosis_service.py
=================================================
Implements the Profit Diagnosis Variance Decomposition Engine.

Per ANALYTICS_FORMULAS.md Section 2, decomposes total Gross Profit
change (delta_GP = GP_B - GP_A) into 5 additive, independent drivers:

    1. Volume Effect       = (W_B - W_A) × MarginRate_A
    2. Discount Effect     = -(disc_per_gram_B - disc_per_gram_A) × W_B
    3. Making-Charge Effect = (mc_per_gram_B - mc_per_gram_A) × W_B
    4. Product-Mix Effect  = SUM_c[(W_Bc/W_B - W_Ac/W_A) × W_B × MarginRate_Ac]
    5. Metal-Margin Effect = Residual = delta_GP - (vol + disc + mc + mix)

The five drivers are additive: vol + disc + mc + mix + metal == delta_GP
(verified internally and by tests).

Multi-tenancy rule (PROJECT_RULES.md Rule 11):
    Every query filters by business_id. Cross-business data leakage is a
    critical data-isolation bug.
"""

import calendar
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Internal: load a month's sales into a DataFrame
# ---------------------------------------------------------------------------

def _load_month_df(db: Session, business_id: int, year: int, month: int) -> pd.DataFrame:
    """
    Returns a DataFrame of sales for (business_id, year, month) with columns:
        weight, selling_price, discount, making_charge, cost_basis, category
    All rows are guaranteed to belong to business_id (multi-tenant filter).
    """
    last_day = calendar.monthrange(year, month)[1]
    start_dt = datetime(year, month, 1)
    end_dt   = datetime(year, month, last_day, 23, 59, 59)

    sql = text("""
        SELECT
            s.weight,
            s.selling_price,
            s.discount,
            s.making_charge,
            s.cost_basis,
            p.category
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        WHERE s.business_id = :business_id
          AND s.sale_date BETWEEN :start_dt AND :end_dt
    """)

    rows = db.execute(sql, {
        "business_id": business_id,
        "start_dt":    start_dt,
        "end_dt":      end_dt,
    }).fetchall()

    if not rows:
        return pd.DataFrame(columns=[
            "weight", "selling_price", "discount",
            "making_charge", "cost_basis", "category",
        ])

    return pd.DataFrame(rows, columns=[
        "weight", "selling_price", "discount",
        "making_charge", "cost_basis", "category",
    ]).astype({
        "weight":        float,
        "selling_price": float,
        "discount":      float,
        "making_charge": float,
        "cost_basis":    float,
        "category":      str,
    })


# ---------------------------------------------------------------------------
# Internal: compute period metrics from a DataFrame
# ---------------------------------------------------------------------------

def _period_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """
    Compute summary metrics from a period's sales DataFrame.
    """
    if df.empty:
        return {
            "row_count":    0,
            "W":            0.0,
            "gross_revenue":0.0,
            "total_discount":0.0,
            "net_revenue":  0.0,
            "cogs":         0.0,
            "gross_profit": 0.0,
            "margin_rate":  0.0,   # GP per gram
            "disc_per_gram":0.0,
            "mc_per_gram":  0.0,
            "category_metrics": {},
        }

    W            = float(df["weight"].sum())
    gross_revenue= float(df["selling_price"].sum())
    total_discount = float(df["discount"].sum())
    net_revenue  = gross_revenue - total_discount
    cogs         = float(df["cost_basis"].sum())
    gross_profit = net_revenue - cogs
    margin_rate  = gross_profit / W if W > 0 else 0.0
    disc_per_gram= total_discount / W if W > 0 else 0.0
    mc_per_gram  = float(df["making_charge"].sum()) / W if W > 0 else 0.0

    # Per-category breakdown (for product-mix effect)
    cat_metrics: dict[str, dict] = {}
    for cat, grp in df.groupby("category"):
        w_c  = float(grp["weight"].sum())
        gp_c = float(
            (grp["selling_price"] - grp["discount"] - grp["cost_basis"]).sum()
        )
        cat_metrics[str(cat)] = {
            "W":           w_c,
            "gross_profit":gp_c,
            "margin_rate": gp_c / w_c if w_c > 0 else 0.0,
        }

    return {
        "row_count":      len(df),
        "W":              W,
        "gross_revenue":  round(gross_revenue,   2),
        "total_discount": round(total_discount,  2),
        "net_revenue":    round(net_revenue,     2),
        "cogs":           round(cogs,            2),
        "gross_profit":   round(gross_profit,    2),
        "margin_rate":    margin_rate,
        "disc_per_gram":  disc_per_gram,
        "mc_per_gram":    mc_per_gram,
        "category_metrics": cat_metrics,
    }


# ---------------------------------------------------------------------------
# Public: analyze_profit_change
# ---------------------------------------------------------------------------

def analyze_profit_change(
    db: Session,
    business_id: int,
    target_year: int,
    target_month: int,
    baseline_year: int,
    baseline_month: int,
) -> dict[str, Any]:
    """
    Decompose the Gross Profit change between two calendar months into
    5 additive drivers per ANALYTICS_FORMULAS.md Section 2.

    Parameters:
        db             — SQLAlchemy session
        business_id    — MANDATORY multi-tenancy filter
        target_year / target_month   — Period B (e.g. June 2026)
        baseline_year / baseline_month — Period A (e.g. May 2026)

    Returns a dict with:
        period_b / period_a — period summary metrics
        drivers             — { volume, discount, making_charge, mix, metal_margin }
        delta_gp            — total GP change (= sum of all drivers)
        additive_check      — True if SUM(drivers) == delta_gp (within 0.01)
    """
    df_b = _load_month_df(db, business_id, target_year, target_month)
    df_a = _load_month_df(db, business_id, baseline_year, baseline_month)

    m_b = _period_metrics(df_b)
    m_a = _period_metrics(df_a)

    W_A = m_a["W"]
    W_B = m_b["W"]
    GP_A = m_a["gross_profit"]
    GP_B = m_b["gross_profit"]

    delta_gp = round(GP_B - GP_A, 2)

    # --- Driver 1: Volume Effect ---
    # (W_B - W_A) × MarginRate_A
    delta_vol = (W_B - W_A) * m_a["margin_rate"]

    # --- Driver 2: Discount Effect ---
    # -(disc_per_gram_B - disc_per_gram_A) × W_B
    delta_disc = -(m_b["disc_per_gram"] - m_a["disc_per_gram"]) * W_B

    # --- Driver 3: Making-Charge Effect ---
    # (mc_per_gram_B - mc_per_gram_A) × W_B
    delta_mc = (m_b["mc_per_gram"] - m_a["mc_per_gram"]) * W_B

    # --- Driver 4: Product-Mix Effect ---
    # SUM_c [ (W_Bc/W_B - W_Ac/W_A) × W_B × MarginRate_Ac ]
    delta_mix = 0.0
    all_cats = set(m_a["category_metrics"].keys()) | set(m_b["category_metrics"].keys())
    for cat in all_cats:
        w_bc  = m_b["category_metrics"].get(cat, {}).get("W", 0.0)
        w_ac  = m_a["category_metrics"].get(cat, {}).get("W", 0.0)
        mr_ac = m_a["category_metrics"].get(cat, {}).get("margin_rate", 0.0)
        share_b = w_bc / W_B if W_B > 0 else 0.0
        share_a = w_ac / W_A if W_A > 0 else 0.0
        delta_mix += (share_b - share_a) * W_B * mr_ac

    # --- Driver 5: Metal Margin Effect (residual) ---
    delta_metal = delta_gp - (delta_vol + delta_disc + delta_mc + delta_mix)

    # Additive check: drivers must sum to delta_gp within 1 rupee
    driver_sum = delta_vol + delta_disc + delta_mc + delta_mix + delta_metal
    additive_ok = abs(driver_sum - delta_gp) < 1.0

    return {
        "business_id": business_id,
        "target":   {"year": target_year,   "month": target_month},
        "baseline": {"year": baseline_year, "month": baseline_month},
        "period_b": {
            "year":            target_year,
            "month":           target_month,
            "transaction_count": m_b["row_count"],
            "total_weight_grams": round(W_B, 4),
            "gross_revenue":   m_b["gross_revenue"],
            "net_revenue":     m_b["net_revenue"],
            "cogs":            m_b["cogs"],
            "gross_profit":    m_b["gross_profit"],
        },
        "period_a": {
            "year":            baseline_year,
            "month":           baseline_month,
            "transaction_count": m_a["row_count"],
            "total_weight_grams": round(W_A, 4),
            "gross_revenue":   m_a["gross_revenue"],
            "net_revenue":     m_a["net_revenue"],
            "cogs":            m_a["cogs"],
            "gross_profit":    m_a["gross_profit"],
        },
        "delta_gp": delta_gp,
        "drivers": {
            "volume":         round(delta_vol,   2),
            "discount":       round(delta_disc,  2),
            "making_charge":  round(delta_mc,    2),
            "product_mix":    round(delta_mix,   2),
            "metal_margin":   round(delta_metal, 2),
        },
        "additive_check": additive_ok,
    }
