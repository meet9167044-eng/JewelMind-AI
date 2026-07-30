"""
backend/app/services/metal_service.py — Metal Exposure & Scenario Engine
=========================================================================
Implements valuation and commodity risk metrics per
ANALYTICS_FORMULAS.md Sections 4 & 5.

IMPORTANT — Rule 21 (PROJECT_RULES.md):
    This service NEVER makes external network calls.
    All rates come ONLY from the `metal_rates` MySQL table (populated by the
    Metal Rate Fetch Service in metal_rate_fetcher.py).

Formulas implemented:

§4.A  Weighted Acquisition Rate (WAR):
      WAR_metal = SUM(metal_cost_k) / SUM(net_weight_k)   for active inventory k

§4.B  Valuation Exposure (per metal):
      Exposure = SUM(net_weight_k × (R_today × purity_ratio_k - WAR_metal))
      where purity_ratio_k = karats/24  (1.0 for Silver)

§5.A  Simulated Board Rate:
      R_sim = R_today × (1 + x/100)

§5.B  Simulated Valuation Exposure:
      Simulated_Exposure = SUM(net_weight_k × (R_sim × purity_ratio_k - WAR_metal))

§5.C  Delta Valuation Movement:
      Delta = SUM(net_weight_k × R_today × (x/100) × purity_ratio_k)
            = Simulated_Exposure - Current_Exposure

Multi-tenancy:
    WAR and exposure calculations are scoped to a single `business_id`.
    The `metal_rates` table is global (no business_id) — it stores market
    reference rates shared by all businesses.
"""

from datetime import date
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.models.metal_rate import MetalRate

# ---------------------------------------------------------------------------
# Purity ratio mapping
# ---------------------------------------------------------------------------

PURITY_RATIOS: dict[str, float] = {
    "24k":   24 / 24,   # 1.0000
    "22k":   22 / 24,   # 0.9167
    "18k":   18 / 24,   # 0.7500
    "14k":   14 / 24,   # 0.5833
    "925":    1.0,       # Sterling silver
    "999":    1.0,       # Fine silver
    "silver": 1.0,       # Generic silver
}


def _purity_ratio(purity: str) -> float:
    """
    Returns the purity ratio for a given purity string.
    Falls back to 1.0 if the purity is unrecognised.
    """
    return PURITY_RATIOS.get(purity.lower(), 1.0)


MetalType = Literal["gold", "silver"]


# ---------------------------------------------------------------------------
# Internal: load active inventory for a metal
# ---------------------------------------------------------------------------

def _load_active_inventory(
    db: Session, business_id: int, metal: MetalType
) -> list[dict[str, Any]]:
    """
    Returns active inventory items (purchased but not fully sold) for a
    given metal and business. Each row contains: net_weight, metal_cost, purity.

    Active = product where SUM(purchase.weight) > SUM(sale.weight).
    We use net_weight from the product table (stable intrinsic weight)
    for valuation, and metal_cost from purchases for WAR.
    """
    sql = text("""
        SELECT
            p.purity,
            p.net_weight,
            COALESCE(pur.total_metal_cost, 0)       AS metal_cost,
            COALESCE(pur.total_net_weight_pur, 0)   AS purchased_net_weight,
            COALESCE(s.total_sold_weight,     0)    AS sold_weight
        FROM products p
        LEFT JOIN (
            SELECT
                product_id,
                SUM(metal_cost) AS total_metal_cost,
                SUM(weight)     AS total_net_weight_pur
            FROM purchases
            WHERE business_id = :business_id
            GROUP BY product_id
        ) pur ON p.product_id = pur.product_id
        LEFT JOIN (
            SELECT product_id, SUM(weight) AS total_sold_weight
            FROM sales
            WHERE business_id = :business_id
            GROUP BY product_id
        ) s ON p.product_id = s.product_id
        WHERE p.business_id = :business_id
          AND LOWER(p.metal) = :metal
          AND (COALESCE(pur.total_net_weight_pur, 0) - COALESCE(s.total_sold_weight, 0)) > 0
    """)
    rows = db.execute(sql, {"business_id": business_id, "metal": metal.lower()}).fetchall()
    return [
        {
            "purity":      row[0],
            "net_weight":  float(row[1]),
            "metal_cost":  float(row[2]),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Internal: get today's rate from DB
# ---------------------------------------------------------------------------

def _get_latest_rate(db: Session, metal: MetalType) -> dict[str, Any]:
    """
    Returns the most recent rate from the `metal_rates` table for the
    requested metal. Never makes an external API call.

    Returns dict with: rate_date, gold_24k, gold_22k, silver
    Raises ValueError if no rates exist in the table.
    """
    rate_row = (
        db.query(MetalRate)
        .order_by(MetalRate.rate_date.desc())
        .first()
    )
    if rate_row is None:
        raise ValueError(
            "No metal rates found in the database. "
            "The Metal Rate Fetch Service has not run yet, or the table is empty."
        )

    if metal == "gold":
        return {
            "rate_date": rate_row.rate_date,
            "gold_24k":  float(rate_row.gold_24k),
            "gold_22k":  float(rate_row.gold_22k),
            "rate_per_gram_24k": float(rate_row.gold_24k),
        }
    else:  # silver
        return {
            "rate_date": rate_row.rate_date,
            "silver":    float(rate_row.silver),
            "rate_per_gram": float(rate_row.silver),
        }


def _gold_rate_for_purity(rate_info: dict, purity_str: str) -> float:
    """
    Returns the per-gram gold rate for a given purity.
    Uses gold_22k directly for 22K, derives others from gold_24k × purity_ratio.
    """
    p = purity_str.lower()
    if p == "22k":
        return rate_info.get("gold_22k", rate_info.get("gold_24k", 0.0))
    ratio = _purity_ratio(purity_str)
    return rate_info.get("gold_24k", 0.0) * ratio


# ---------------------------------------------------------------------------
# Public: calculate_metal_exposure
# ---------------------------------------------------------------------------

def calculate_metal_exposure(
    db: Session,
    business_id: int,
    metal: MetalType,
) -> dict[str, Any]:
    """
    Computes the Weighted Acquisition Rate and Valuation Exposure for
    active inventory of the specified metal, using the latest stored rate.

    Formula §4.A — WAR:
        WAR = SUM(metal_cost) / SUM(net_weight)

    Formula §4.B — Exposure:
        Exposure = SUM(net_weight × (R_today × purity_ratio - WAR))

    Returns zero-exposure result if no inventory exists for this metal.
    """
    items    = _load_active_inventory(db, business_id, metal)
    rate_row = _get_latest_rate(db, metal)

    if not items:
        return {
            "business_id":    business_id,
            "metal":          metal,
            "as_of_date":     str(rate_row["rate_date"]),
            "item_count":     0,
            "total_net_weight_grams": 0.0,
            "war":            None,
            "valuation_exposure": 0.0,
            "current_rate":   rate_row,
        }

    # WAR = SUM(metal_cost) / SUM(net_weight)
    total_metal_cost = sum(item["metal_cost"]  for item in items)
    total_net_weight = sum(item["net_weight"]  for item in items)
    war = total_metal_cost / total_net_weight if total_net_weight > 0 else 0.0

    # Exposure = SUM(net_weight × (R × purity_ratio - WAR))
    exposure = 0.0
    for item in items:
        purity_ratio = _purity_ratio(item["purity"])
        if metal == "gold":
            r_today = _gold_rate_for_purity(rate_row, item["purity"])
        else:
            r_today = rate_row["rate_per_gram"]

        exposure += item["net_weight"] * (r_today * purity_ratio - war)

    return {
        "business_id":            business_id,
        "metal":                  metal,
        "as_of_date":             str(rate_row["rate_date"]),
        "item_count":             len(items),
        "total_net_weight_grams": round(total_net_weight, 4),
        "war":                    round(war, 2),
        "valuation_exposure":     round(exposure, 2),
        "current_rate":           rate_row,
        "note": (
            "Valuation Exposure is a paper valuation fluctuation, "
            "not a realized financial gain or loss."
        ),
    }


# ---------------------------------------------------------------------------
# Public: simulate_metal_rate_shift
# ---------------------------------------------------------------------------

def simulate_metal_rate_shift(
    db: Session,
    business_id: int,
    metal: MetalType,
    change_percent: float,
) -> dict[str, Any]:
    """
    Simulates the impact of a metal rate shift on inventory valuation.

    Formula §5.A — Simulated Rate:
        R_sim = R_today × (1 + x/100)

    Formula §5.C — Delta Value:
        Delta = SUM(net_weight × R_today × (x/100) × purity_ratio)

    Parameters:
        change_percent — percentage shift (e.g. -10 for a 10% drop, +5 for 5% rise)

    Uses ONLY stored DB rates — zero external network calls.
    """
    items    = _load_active_inventory(db, business_id, metal)
    rate_row = _get_latest_rate(db, metal)

    if not items:
        return {
            "business_id":         business_id,
            "metal":               metal,
            "change_percent":      change_percent,
            "as_of_date":          str(rate_row["rate_date"]),
            "item_count":          0,
            "total_net_weight_grams": 0.0,
            "current_exposure":    0.0,
            "simulated_exposure":  0.0,
            "delta_value":         0.0,
        }

    # Compute current exposure first
    total_metal_cost = sum(item["metal_cost"] for item in items)
    total_net_weight = sum(item["net_weight"] for item in items)
    war = total_metal_cost / total_net_weight if total_net_weight > 0 else 0.0

    x = change_percent / 100.0

    current_exposure   = 0.0
    simulated_exposure = 0.0
    delta              = 0.0

    for item in items:
        purity_ratio = _purity_ratio(item["purity"])
        if metal == "gold":
            r_today = _gold_rate_for_purity(rate_row, item["purity"])
        else:
            r_today = rate_row["rate_per_gram"]

        r_sim = r_today * (1 + x)

        current_exposure   += item["net_weight"] * (r_today * purity_ratio - war)
        simulated_exposure += item["net_weight"] * (r_sim   * purity_ratio - war)
        delta              += item["net_weight"] * r_today * x * purity_ratio  # §5.C

    return {
        "business_id":            business_id,
        "metal":                  metal,
        "change_percent":         change_percent,
        "as_of_date":             str(rate_row["rate_date"]),
        "item_count":             len(items),
        "total_net_weight_grams": round(total_net_weight, 4),
        "war":                    round(war, 2),
        "current_exposure":       round(current_exposure,   2),
        "simulated_exposure":     round(simulated_exposure, 2),
        "delta_value":            round(delta,              2),
        "note": (
            "Delta Value represents a paper valuation movement, "
            "not a realized financial gain or loss."
        ),
    }


# ---------------------------------------------------------------------------
# Public: get_latest_metal_rates (read-only, zero external calls)
# ---------------------------------------------------------------------------

def get_latest_metal_rates(db: Session) -> dict[str, Any]:
    """
    Returns the most recently stored metal rates from MySQL.
    Safe to call from analytics — zero external network calls.
    """
    rate_row = db.query(MetalRate).order_by(MetalRate.rate_date.desc()).first()
    if rate_row is None:
        return {"available": False, "rates": None}
    return {
        "available": True,
        "rates": {
            "rate_date": str(rate_row.rate_date),
            "gold_24k":  float(rate_row.gold_24k),
            "gold_22k":  float(rate_row.gold_22k),
            "silver":    float(rate_row.silver),
        },
    }
