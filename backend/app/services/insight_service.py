"""
backend/app/services/insight_service.py — Proactive Insight Engine
===================================================================
Rule-based engine that scans analytics outputs and produces a prioritised,
business-scoped Action Center alert list.

Rules implemented (PROJECT_PLAN.md §Phase 15):

    Rule 1 — Aged Inventory Alert (HIGH)
        Trigger: Any inventory bucket >180 days old with total value > ₹100,000.
        Data source: inventory_service.calculate_inventory_age()

    Rule 2 — Stockout Warning (MEDIUM)
        Trigger: Any fast-moving product with stock coverage < 15 days.
        Data source: inventory_service.classify_inventory_performance()

    Rule 3 — Discount Escalation (LOW)
        Trigger: Average discount rate increased > 25% month-over-month.
        Data source: profit_diagnosis_service.analyze_profit_change() driver.

Multi-tenancy:
    Every rule check receives business_id and calls analytics functions that
    are already scoped by business_id. Cross-business data leakage is impossible
    at the insight layer because the underlying analytics functions enforce it.
"""

import calendar
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.services import inventory_service, profit_diagnosis_service


PRIORITY_HIGH   = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW    = "low"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _current_period() -> tuple[int, int]:
    """Returns (year, month) of the current calendar month."""
    now = date.today()
    return now.year, now.month


def _previous_period() -> tuple[int, int]:
    """Returns (year, month) of the previous calendar month."""
    now = date.today()
    if now.month == 1:
        return now.year - 1, 12
    return now.year, now.month - 1


def _bucket_total_value(db: Session, business_id: int, min_age_days: int) -> dict[str, Any]:
    """
    Returns total value and count of unsold inventory older than `min_age_days` days.
    Calculates inline rather than relying on ageing buckets to get exact totals
    above threshold.
    """
    sql = text("""
        SELECT
            COUNT(p.product_id)             AS item_count,
            COALESCE(SUM(pur.metal_cost), 0) AS total_value
        FROM products p
        LEFT JOIN (
            SELECT product_id, SUM(metal_cost) AS metal_cost, MAX(purchase_date) AS last_purchase
            FROM purchases
            WHERE business_id = :bid
            GROUP BY product_id
        ) pur ON p.product_id = pur.product_id
        LEFT JOIN (
            SELECT product_id, SUM(weight) AS sold_wt
            FROM sales WHERE business_id = :bid
            GROUP BY product_id
        ) s ON p.product_id = s.product_id
        WHERE p.business_id = :bid
          AND COALESCE(s.sold_wt, 0) < p.gross_weight
          AND pur.last_purchase IS NOT NULL
          AND DATEDIFF(CURRENT_DATE, pur.last_purchase) > :min_age
    """)
    try:
        row = db.execute(sql, {"bid": business_id, "min_age": min_age_days}).fetchone()
        return {
            "item_count":  int(row[0]) if row else 0,
            "total_value": float(row[1]) if row else 0.0,
        }
    except Exception:
        # SQLite fallback for tests (no DATEDIFF)
        sql_lite = text("""
            SELECT
                COUNT(p.product_id),
                COALESCE(SUM(pur.metal_cost), 0)
            FROM products p
            LEFT JOIN (
                SELECT product_id, SUM(metal_cost) AS metal_cost,
                       MAX(purchase_date) AS last_purchase
                FROM purchases
                WHERE business_id = :bid
                GROUP BY product_id
            ) pur ON p.product_id = pur.product_id
            LEFT JOIN (
                SELECT product_id, SUM(weight) AS sold_wt
                FROM sales WHERE business_id = :bid
                GROUP BY product_id
            ) s ON p.product_id = s.product_id
            WHERE p.business_id = :bid
              AND COALESCE(s.sold_wt, 0) < p.gross_weight
              AND pur.last_purchase IS NOT NULL
              AND CAST(julianday('now') - julianday(pur.last_purchase) AS INTEGER) > :min_age
        """)
        row = db.execute(sql_lite, {"bid": business_id, "min_age": min_age_days}).fetchone()
        return {
            "item_count":  int(row[0]) if row else 0,
            "total_value": float(row[1]) if row else 0.0,
        }


def _average_discount_rate(db: Session, business_id: int, year: int, month: int) -> float:
    """
    Returns average discount rate as a fraction (e.g. 0.032 = 3.2%) for a given month.
    discount_rate = total_discount / total_selling_price.
    """
    last_day = calendar.monthrange(year, month)[1]
    start_dt = datetime(year, month, 1)
    end_dt   = datetime(year, month, last_day, 23, 59, 59)
    sql = text("""
        SELECT
            COALESCE(SUM(discount), 0)       AS total_disc,
            COALESCE(SUM(selling_price), 0)  AS total_rev
        FROM sales
        WHERE business_id = :bid
          AND sale_date BETWEEN :s AND :e
    """)
    row = db.execute(sql, {"bid": business_id, "s": start_dt, "e": end_dt}).fetchone()
    if not row or row[1] == 0:
        return 0.0
    return float(row[0]) / float(row[1])


# ---------------------------------------------------------------------------
# Public: run_all_rules — generates the Action Center alert list
# ---------------------------------------------------------------------------

def run_all_rules(db: Session, business_id: int) -> list[dict[str, Any]]:
    """
    Executes all three insight rules scoped to `business_id`.
    Returns a list of alert dicts sorted by priority (high → medium → low).

    Each alert dict:
        {
            "rule_id":    str,    # unique rule identifier
            "priority":   str,    # "high" | "medium" | "low"
            "title":      str,    # short human-readable alert title
            "detail":     str,    # detailed description with exact numbers
            "action_link": str,   # frontend relative path hint (e.g. "inventory")
            "evidence":   dict,   # raw data that triggered this alert
        }
    """
    alerts: list[dict[str, Any]] = []

    # ── Rule 1: Aged Inventory Alert (HIGH) ─────────────────────────────────
    try:
        aged = _bucket_total_value(db, business_id, min_age_days=180)
        if aged["item_count"] > 0 and aged["total_value"] >= 100_000:
            alerts.append({
                "rule_id":    "aged_inventory_high",
                "priority":   PRIORITY_HIGH,
                "title":      "Aged Inventory Above ₹1L",
                "detail": (
                    f"{aged['item_count']} unsold items have been in your inventory for over 180 days "
                    f"with a combined acquisition cost of ₹{aged['total_value']:,.0f}. "
                    "Consider targeted discounting, bundling, or melting to release tied-up capital."
                ),
                "action_link": "inventory",
                "evidence": aged,
            })
        elif aged["item_count"] > 0:
            # Aged stock exists but below ₹1L threshold — still surface as medium
            alerts.append({
                "rule_id":    "aged_inventory_medium",
                "priority":   PRIORITY_MEDIUM,
                "title":      "Inventory Ageing Detected",
                "detail": (
                    f"{aged['item_count']} items are over 180 days old "
                    f"(acquisition cost ₹{aged['total_value']:,.0f}). Monitoring recommended."
                ),
                "action_link": "inventory",
                "evidence": aged,
            })
    except Exception as exc:
        pass  # Rule failures never crash the endpoint

    # ── Rule 2: Stockout Warning (MEDIUM) ────────────────────────────────────
    try:
        perf = inventory_service.classify_inventory_performance(db, business_id)
        stockout_risks = perf.get("stockout_risks", [])
        if stockout_risks:
            alerts.append({
                "rule_id":    "stockout_warning",
                "priority":   PRIORITY_MEDIUM,
                "title":      f"Stockout Risk — {len(stockout_risks)} Fast Movers",
                "detail": (
                    f"{len(stockout_risks)} fast-moving products have fewer than 15 days of stock coverage "
                    "remaining at their current sales velocity. Replenish stock to avoid missed sales."
                ),
                "action_link": "inventory",
                "evidence": {
                    "count": len(stockout_risks),
                    "items": [
                        {
                            "product_name": i.get("product_name", i.get("sku")),
                            "category":     i.get("category"),
                            "coverage_days": round(i.get("stock_coverage_days", 0), 1),
                        }
                        for i in stockout_risks[:10]  # cap at 10 for payload size
                    ],
                },
            })
    except Exception:
        pass

    # ── Rule 3: Discount Escalation (LOW) ────────────────────────────────────
    try:
        cy, cm = _current_period()
        py, pm = _previous_period()
        curr_disc = _average_discount_rate(db, business_id, cy, cm)
        prev_disc = _average_discount_rate(db, business_id, py, pm)

        # Check if discount rate increased by more than 25% relative
        if prev_disc > 0 and curr_disc > 0:
            change_pct = (curr_disc - prev_disc) / prev_disc * 100
            if change_pct > 25.0:
                alerts.append({
                    "rule_id":    "discount_escalation",
                    "priority":   PRIORITY_LOW,
                    "title":      "Discount Rate Escalating",
                    "detail": (
                        f"Your average discount rate has increased from "
                        f"{prev_disc * 100:.1f}% to {curr_disc * 100:.1f}% "
                        f"(+{change_pct:.1f}% relative change month-over-month). "
                        "Review discount policy to protect gross margins."
                    ),
                    "action_link": "profit",
                    "evidence": {
                        "current_period":  f"{cy}-{str(cm).zfill(2)}",
                        "previous_period": f"{py}-{str(pm).zfill(2)}",
                        "current_discount_rate_pct":  round(curr_disc * 100, 2),
                        "previous_discount_rate_pct": round(prev_disc * 100, 2),
                        "change_pct": round(change_pct, 2),
                    },
                })
    except Exception:
        pass

    # Sort: high → medium → low
    priority_order = {PRIORITY_HIGH: 0, PRIORITY_MEDIUM: 1, PRIORITY_LOW: 2}
    alerts.sort(key=lambda a: priority_order.get(a["priority"], 99))

    return alerts
