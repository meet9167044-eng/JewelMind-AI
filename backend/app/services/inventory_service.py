"""
backend/app/services/inventory_service.py — Inventory Intelligence Engine
=========================================================================
Implements inventory ageing, stock coverage, and classification logic
per ANALYTICS_FORMULAS.md Section 3 and PROJECT_PLAN.md Phase 10.

Inventory Model:
    - Active inventory = products where SUM(purchase.weight) > SUM(sale.weight)
    - Acquisition date = oldest purchase_date for that product (FIFO proxy)
    - Age = (as_of_date - oldest_purchase_date).days

Ageing Buckets (ANALYTICS_FORMULAS.md §3.A):
    0-30d | 31-90d | 91-180d | 181-365d | 365+d

Stock Coverage (§3.B):
    Coverage_c = inventory_weight_c / avg_daily_sales_weight_c(30d)

Classification Rules (§3.C):
    - Dead Stock       : age > 180 days AND 0 sales on that product in past 90 days
    - Slow Mover       : coverage > 180 days
    - Stockout Risk    : fast mover AND coverage < 15 days
    - Fast Mover       : top 20% of products by sales velocity (weight/day over 30d)

Multi-tenancy rule (PROJECT_RULES.md Rule 11):
    Every query MUST filter by business_id. Cross-business leakage is a
    critical data-isolation bug.
"""

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_inventory_df(db: Session, business_id: int) -> pd.DataFrame:
    """
    Loads per-product inventory position by computing:
        purchased_weight - sold_weight = remaining_weight
    and the oldest purchase_date per product for age calculation.

    Returns only products with remaining_weight > 0.
    """
    sql = text("""
        SELECT
            p.product_id,
            p.sku,
            p.product_name,
            p.category,
            p.metal,
            p.purity,
            COALESCE(pur.total_purchased_weight, 0)  AS purchased_weight,
            COALESCE(pur.total_purchased_qty,    0)  AS purchased_qty,
            COALESCE(s.total_sold_weight,        0)  AS sold_weight,
            COALESCE(s.total_sold_qty,           0)  AS sold_qty,
            COALESCE(pur.total_purchased_weight, 0) - COALESCE(s.total_sold_weight, 0) AS remaining_weight,
            pur.oldest_purchase_date,
            COALESCE(pur.total_cost,             0)  AS total_cost
        FROM products p
        LEFT JOIN (
            SELECT
                product_id,
                SUM(weight)        AS total_purchased_weight,
                SUM(quantity)      AS total_purchased_qty,
                MIN(purchase_date) AS oldest_purchase_date,
                SUM(total_cost)    AS total_cost
            FROM purchases
            WHERE business_id = :business_id
            GROUP BY product_id
        ) pur ON p.product_id = pur.product_id
        LEFT JOIN (
            SELECT
                product_id,
                SUM(weight)   AS total_sold_weight,
                SUM(quantity) AS total_sold_qty
            FROM sales
            WHERE business_id = :business_id
            GROUP BY product_id
        ) s ON p.product_id = s.product_id
        WHERE p.business_id = :business_id
          AND (COALESCE(pur.total_purchased_weight, 0) - COALESCE(s.total_sold_weight, 0)) > 0
    """)

    rows = db.execute(sql, {"business_id": business_id}).fetchall()
    if not rows:
        return pd.DataFrame(columns=[
            "product_id", "sku", "product_name", "category", "metal", "purity",
            "purchased_weight", "purchased_qty", "sold_weight", "sold_qty",
            "remaining_weight", "oldest_purchase_date", "total_cost",
        ])

    df = pd.DataFrame(rows, columns=[
        "product_id", "sku", "product_name", "category", "metal", "purity",
        "purchased_weight", "purchased_qty", "sold_weight", "sold_qty",
        "remaining_weight", "oldest_purchase_date", "total_cost",
    ])
    df["purchased_weight"]  = df["purchased_weight"].astype(float)
    df["sold_weight"]       = df["sold_weight"].astype(float)
    df["remaining_weight"]  = df["remaining_weight"].astype(float)
    df["total_cost"]        = df["total_cost"].astype(float)
    return df


def _load_recent_sales_df(db: Session, business_id: int, since: datetime) -> pd.DataFrame:
    """
    Returns sales (weight, product_id, category) since a given datetime.
    Used for stock coverage and dead-stock classification.
    """
    sql = text("""
        SELECT s.product_id, s.weight, p.category
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        WHERE s.business_id = :business_id
          AND s.sale_date   >= :since_dt
    """)
    rows = db.execute(sql, {"business_id": business_id, "since_dt": since}).fetchall()
    if not rows:
        return pd.DataFrame(columns=["product_id", "weight", "category"])
    df = pd.DataFrame(rows, columns=["product_id", "weight", "category"])
    df["weight"] = df["weight"].astype(float)
    return df


def _age_bucket(age_days: int) -> str:
    if age_days <= 30:   return "0-30d"
    if age_days <= 90:   return "31-90d"
    if age_days <= 180:  return "91-180d"
    if age_days <= 365:  return "181-365d"
    return "365+d"


# ---------------------------------------------------------------------------
# Public: calculate_inventory_age
# ---------------------------------------------------------------------------

def calculate_inventory_age(
    db: Session,
    business_id: int,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """
    Calculates inventory ageing for business_id.

    Returns ageing buckets by item count and by value (total_cost),
    plus a per-item detail list sorted by age descending.

    Parameters:
        as_of_date — reference date for age calculation (default: today)
    """
    if as_of_date is None:
        as_of_date = date.today()

    inv = _load_inventory_df(db, business_id)

    if inv.empty:
        buckets = {b: {"count": 0, "weight": 0.0, "value": 0.0}
                   for b in ["0-30d", "31-90d", "91-180d", "181-365d", "365+d"]}
        return {
            "business_id":    business_id,
            "as_of_date":     as_of_date.isoformat(),
            "total_items":    0,
            "total_weight":   0.0,
            "total_value":    0.0,
            "buckets":        buckets,
            "items":          [],
        }

    # Calculate age per item
    inv["age_days"] = inv["oldest_purchase_date"].apply(
        lambda d: (as_of_date - pd.to_datetime(d).date()).days if d is not None else 0
    )
    inv["age_bucket"] = inv["age_days"].apply(_age_bucket)

    # Bucket summary
    buckets: dict[str, dict] = {}
    for bucket in ["0-30d", "31-90d", "91-180d", "181-365d", "365+d"]:
        subset = inv[inv["age_bucket"] == bucket]
        buckets[bucket] = {
            "count":  int(len(subset)),
            "weight": round(float(subset["remaining_weight"].sum()), 4),
            "value":  round(float(subset["total_cost"].sum()), 2),
        }

    # Item detail list
    items = []
    for _, row in inv.sort_values("age_days", ascending=False).iterrows():
        items.append({
            "product_id":    int(row["product_id"]),
            "sku":           row["sku"],
            "product_name":  row["product_name"],
            "category":      row["category"],
            "metal":         row["metal"],
            "purity":        row["purity"],
            "remaining_weight": round(float(row["remaining_weight"]), 4),
            "age_days":      int(row["age_days"]),
            "age_bucket":    row["age_bucket"],
            "oldest_purchase_date": str(row["oldest_purchase_date"]),
            "total_cost":    round(float(row["total_cost"]), 2),
        })

    return {
        "business_id":  business_id,
        "as_of_date":   as_of_date.isoformat(),
        "total_items":  len(inv),
        "total_weight": round(float(inv["remaining_weight"].sum()), 4),
        "total_value":  round(float(inv["total_cost"].sum()), 2),
        "buckets":      buckets,
        "items":        items,
    }


# ---------------------------------------------------------------------------
# Public: classify_inventory_performance
# ---------------------------------------------------------------------------

def classify_inventory_performance(
    db: Session,
    business_id: int,
    as_of_date: date | None = None,
    coverage_lookback_days: int = 30,
) -> dict[str, Any]:
    """
    Classifies inventory items into:
        - dead_stock      : age > 180 days AND 0 sales in last 90 days
        - slow_movers     : stock coverage > 180 days
        - stockout_risks  : fast mover AND coverage < 15 days

    Parameters:
        as_of_date            — reference date (default: today)
        coverage_lookback_days — window for avg daily sales (default: 30)
    """
    if as_of_date is None:
        as_of_date = date.today()

    as_of_dt  = datetime.combine(as_of_date, datetime.max.time())
    window_30d = datetime.combine(as_of_date - timedelta(days=coverage_lookback_days),
                                  datetime.min.time())
    window_90d = datetime.combine(as_of_date - timedelta(days=90),
                                  datetime.min.time())

    inv          = _load_inventory_df(db, business_id)
    sales_30d    = _load_recent_sales_df(db, business_id, window_30d)
    sales_90d    = _load_recent_sales_df(db, business_id, window_90d)

    # --- Per-product age ---
    if not inv.empty:
        inv["age_days"] = inv["oldest_purchase_date"].apply(
            lambda d: (as_of_date - pd.to_datetime(d).date()).days if d is not None else 0
        )
    else:
        inv["age_days"] = []

    # --- Sales velocity per product (30d) ---
    sales_30d_by_product = (
        sales_30d.groupby("product_id")["weight"].sum()
        if not sales_30d.empty else pd.Series(dtype=float)
    )
    sales_90d_products = (
        set(sales_90d["product_id"].unique())
        if not sales_90d.empty else set()
    )

    # --- Category-level stock coverage ---
    # Coverage_c = remaining_weight_c / (30d_sold_weight_c / 30)
    cat_remaining = (
        inv.groupby("category")["remaining_weight"].sum()
        if not inv.empty else pd.Series(dtype=float)
    )
    cat_sold_30d = (
        sales_30d.groupby("category")["weight"].sum()
        if not sales_30d.empty else pd.Series(dtype=float)
    )

    # Fast movers: top 20% of products by 30d sales velocity
    if not sales_30d.empty:
        velocity = sales_30d.groupby("product_id")["weight"].sum()
        thresh = velocity.quantile(0.80) if len(velocity) >= 5 else float("-inf")
        fast_mover_products = set(velocity[velocity >= thresh].index.tolist())
    else:
        fast_mover_products = set()

    # --- Build classification lists ---
    dead_stock:     list[dict] = []
    slow_movers:    list[dict] = []
    stockout_risks: list[dict] = []

    for _, row in inv.iterrows():
        pid        = int(row["product_id"])
        age        = int(row["age_days"])
        cat        = row["category"]
        rem_weight = float(row["remaining_weight"])

        # Stock coverage for this item's category
        cat_rem   = float(cat_remaining.get(cat, 0.0))
        cat_sold  = float(cat_sold_30d.get(cat, 0.0))
        avg_daily = cat_sold / coverage_lookback_days if cat_sold > 0 else 0.0
        coverage  = cat_rem / avg_daily if avg_daily > 0 else float("inf")

        item_summary = {
            "product_id":       pid,
            "sku":              row["sku"],
            "product_name":     row["product_name"],
            "category":         cat,
            "metal":            row["metal"],
            "purity":           row["purity"],
            "remaining_weight": round(rem_weight, 4),
            "age_days":         age,
            "coverage_days":    round(coverage, 1) if coverage != float("inf") else None,
            "total_cost":       round(float(row["total_cost"]), 2),
        }

        # Dead stock: age > 180d AND no sales on this product in last 90 days
        if age > 180 and pid not in sales_90d_products:
            dead_stock.append(item_summary)

        # Slow mover: coverage > 180 days (includes inf)
        if coverage > 180:
            slow_movers.append(item_summary)

        # Stockout risk: fast mover AND coverage < 15 days
        if pid in fast_mover_products and coverage < 15:
            stockout_risks.append({**item_summary, "is_fast_mover": True})

    # --- Category coverage summary ---
    coverage_by_category: dict[str, dict] = {}
    all_cats = set(cat_remaining.index.tolist()) | set(cat_sold_30d.index.tolist())
    for cat in all_cats:
        rem   = float(cat_remaining.get(cat, 0.0))
        sold  = float(cat_sold_30d.get(cat, 0.0))
        avg_d = sold / coverage_lookback_days if sold > 0 else 0.0
        cov   = rem / avg_d if avg_d > 0 else None
        coverage_by_category[cat] = {
            "remaining_weight_grams":        round(rem,  4),
            "sold_weight_30d_grams":         round(sold, 4),
            "avg_daily_sales_weight_grams":  round(avg_d, 6),
            "coverage_days":                 round(cov, 1) if cov is not None else None,
        }

    return {
        "business_id":          business_id,
        "as_of_date":           as_of_date.isoformat(),
        "coverage_lookback_days": coverage_lookback_days,
        "summary": {
            "dead_stock_count":    len(dead_stock),
            "slow_mover_count":    len(slow_movers),
            "stockout_risk_count": len(stockout_risks),
        },
        "dead_stock":             dead_stock,
        "slow_movers":            slow_movers,
        "stockout_risks":         stockout_risks,
        "coverage_by_category":   coverage_by_category,
    }
