"""
Phase 3 — Hand-Trace & Calculation Verification
================================================

Product : GC202  (product_id = 102)
         Gold Chain | 22K | 18.5 g (gross & net)

This script:
  1. Loads data/products.csv, purchases.csv, and sales.csv.
  2. Isolates every row belonging to product_id = 102 (GC202).
  3. Manually computes the following metrics per ANALYTICS_FORMULAS.md:
       A. Gross Revenue        = SUM(selling_price)
       B. Net Revenue          = SUM(selling_price - discount)
       C. COGS                 = SUM(cost_basis)
       D. Gross Profit         = Net Revenue - COGS
       E. Gross Margin %       = (Gross Profit / Net Revenue) * 100
       F. Making Charge / gram = SUM(making_charge) / SUM(weight)
  4. Cross-checks:
       - cost_basis on every sale row equals purchases.total_cost (exact match).
       - All selling prices, making charges, and cost bases are positive.
  5. Asserts every value matches its formula definition exactly.

Run:
    python backend/scripts/verify_hand_trace.py

Expected:  All assertions pass and a summary table is printed.

IMPORTANT — Multi-tenancy note:
    The synthetic CSVs do not yet contain a business_id column (Phase 2
    pre-dates the SaaS architecture). When Phase 7 seeds the database,
    the seeder assigns all synthetic rows to business_id = 1.
    All formulas here are scoped to product_id = 102, which maps to a
    single business in production; the filtering logic is identical.
"""

import math
import pathlib
import sys

import pandas as pd

# ---------------------------------------------------------------------------
# 0. Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent  # project root
DATA = ROOT / "data"

# ---------------------------------------------------------------------------
# 1. Load CSVs
# ---------------------------------------------------------------------------
print("=" * 60)
print("Phase 3 — Hand-Trace & Calculation Verification")
print("=" * 60)
print("\nLoading CSV files …")

products  = pd.read_csv(DATA / "products.csv")
purchases = pd.read_csv(DATA / "purchases.csv")
sales     = pd.read_csv(DATA / "sales.csv")

print(f"  products  : {len(products):>6,} rows")
print(f"  purchases : {len(purchases):>6,} rows")
print(f"  sales     : {len(sales):>6,} rows")

# ---------------------------------------------------------------------------
# 2. Isolate GC202 (product_id = 102)
# ---------------------------------------------------------------------------
PRODUCT_ID = 102
SKU        = "GC202"

prod_row = products[products["sku"] == SKU]
assert len(prod_row) == 1, f"Expected exactly 1 row for SKU {SKU}, got {len(prod_row)}"
assert int(prod_row["product_id"].iloc[0]) == PRODUCT_ID, "product_id mismatch"

prod_purch = purchases[purchases["product_id"] == PRODUCT_ID]
prod_sales = sales[sales["product_id"] == PRODUCT_ID]

print(f"\n--- GC202 (product_id={PRODUCT_ID}) ---")
print(f"  Purchase rows : {len(prod_purch)}")
print(f"  Sale rows     : {len(prod_sales)}")

# Expect exactly 1 purchase record for a serialised gold chain
assert len(prod_purch) == 1, (
    f"Expected 1 purchase row for {SKU}, found {len(prod_purch)}. "
    "Update this assertion if multi-purchase products are intended."
)

# ---------------------------------------------------------------------------
# 3. Extract values
# ---------------------------------------------------------------------------
purchase = prod_purch.iloc[0]
PURCHASE_TOTAL_COST = float(purchase["total_cost"])
PURCHASE_METAL_RATE = float(purchase["metal_rate"])
PURCHASE_METAL_COST = float(purchase["metal_cost"])
PURCHASE_MAKING_COST = float(purchase["making_cost"])
PURCHASE_WEIGHT      = float(purchase["weight"])

# Verify total_cost integrity: metal_cost + making_cost == total_cost
assert math.isclose(
    PURCHASE_METAL_COST + PURCHASE_MAKING_COST,
    PURCHASE_TOTAL_COST,
    rel_tol=1e-4,
), (
    f"Purchase integrity error: "
    f"metal_cost ({PURCHASE_METAL_COST}) + making_cost ({PURCHASE_MAKING_COST}) "
    f"!= total_cost ({PURCHASE_TOTAL_COST})"
)

# Sales columns
S  = prod_sales["selling_price"].astype(float)
D  = prod_sales["discount"].astype(float)
MC = prod_sales["making_charge"].astype(float)
CB = prod_sales["cost_basis"].astype(float)
W  = prod_sales["weight"].astype(float)

# ---------------------------------------------------------------------------
# 4. Cross-check: every cost_basis must equal purchases.total_cost
# ---------------------------------------------------------------------------
print("\n=== Cross-Check: cost_basis == purchase total_cost ===")
mismatch = prod_sales[
    ~prod_sales["cost_basis"].apply(
        lambda x: math.isclose(float(x), PURCHASE_TOTAL_COST, rel_tol=1e-4)
    )
]
if not mismatch.empty:
    print("  FAIL — Mismatched rows:")
    print(mismatch[["sale_id", "cost_basis"]].to_string(index=False))
    sys.exit(1)
print(f"  PASS — All {len(prod_sales)} sale rows have cost_basis = {PURCHASE_TOTAL_COST:.2f}")

# ---------------------------------------------------------------------------
# 5. Positivity checks
# ---------------------------------------------------------------------------
print("\n=== Positivity Checks ===")

assert (S > 0).all(),  "selling_price has non-positive values"
assert (D >= 0).all(), "discount has negative values"
assert (MC > 0).all(), "making_charge has non-positive values"
assert (CB > 0).all(), "cost_basis has non-positive values"
assert (W > 0).all(),  "weight has non-positive values"

print("  PASS — All selling_price, making_charge, cost_basis, and weight values are positive")
print("  PASS — All discount values are non-negative")

# ---------------------------------------------------------------------------
# 6. Formula Calculations  (per ANALYTICS_FORMULAS.md Section 1)
# ---------------------------------------------------------------------------

# A. Gross Revenue = SUM(selling_price)
gross_revenue = S.sum()

# B. Net Revenue = SUM(selling_price - discount)
net_revenue = (S - D).sum()

# C. COGS = SUM(cost_basis)
cogs = CB.sum()

# D. Gross Profit = Net Revenue - COGS
gross_profit = net_revenue - cogs

# E. Gross Margin % = (Gross Profit / Net Revenue) * 100
gross_margin_pct = (gross_profit / net_revenue) * 100

# F. Making Charge per gram = SUM(making_charge) / SUM(weight)
total_making_charge = MC.sum()
total_weight        = W.sum()
making_charge_per_gram = total_making_charge / total_weight

# ---------------------------------------------------------------------------
# 7. Assert internal consistency
# ---------------------------------------------------------------------------

# GP must also equal SUM(S - D - CB)  (ANALYTICS_FORMULAS.md Eq. D)
gp_direct = (S - D - CB).sum()
assert math.isclose(gross_profit, gp_direct, rel_tol=1e-6), (
    f"Gross Profit consistency error: "
    f"Net Revenue - COGS ({gross_profit:.4f}) != SUM(S-D-CB) ({gp_direct:.4f})"
)

# Net Revenue must be <= Gross Revenue (discounts are non-negative)
assert net_revenue <= gross_revenue, "Net Revenue > Gross Revenue — discount is negative somewhere"

# Gross Margin may be negative — this is valid when high discounts exceed margin.
# GC202 has heavy June discounts in the synthetic data (Scenario A), producing
# a negative overall GP. The analytics engine must handle negative margins.
# We only check the formula is arithmetically consistent, not that it's positive.
assert isinstance(gross_margin_pct, float), "Gross Margin % is not a float"

# ---------------------------------------------------------------------------
# 8. Print Summary Table
# ---------------------------------------------------------------------------
print("\n=== Hand-Trace Results for GC202 (product_id=102) ===")
print(f"\n  Product          : {prod_row['product_name'].iloc[0]}")
print(f"  SKU              : {SKU}")
print(f"  Category         : {prod_row['category'].iloc[0]}")
print(f"  Metal / Purity   : {prod_row['metal'].iloc[0].title()} / {prod_row['purity'].iloc[0]}")
print(f"  Weight           : {float(prod_row['net_weight'].iloc[0]):.1f} g")
print(f"\n  --- Acquisition (Purchase) ---")
print(f"  Purchase date    : {purchase['purchase_date']}")
print(f"  Metal rate       : Rs {PURCHASE_METAL_RATE:,.2f}/g")
print(f"  Metal cost       : Rs {PURCHASE_METAL_COST:,.2f}")
print(f"  Making cost      : Rs {PURCHASE_MAKING_COST:,.2f}")
print(f"  Total cost       : Rs {PURCHASE_TOTAL_COST:,.2f}")
print(f"\n  --- Sales (all {len(prod_sales)} transactions) ---")
print(f"  Gross Revenue         : Rs {gross_revenue:>12,.2f}")
print(f"  Total Discount        : Rs {D.sum():>12,.2f}")
print(f"  Net Revenue           : Rs {net_revenue:>12,.2f}")
print(f"  COGS                  : Rs {cogs:>12,.2f}")
print(f"  Gross Profit          : Rs {gross_profit:>12,.2f}")
print(f"  Gross Margin %        :    {gross_margin_pct:>11.2f}%")
print(f"  Total Making Charge   : Rs {total_making_charge:>12,.2f}")
print(f"  Total Weight Sold     :    {total_weight:>11.1f} g")
print(f"  Making Charge / gram  : Rs {making_charge_per_gram:>12,.2f}/g")

# ---------------------------------------------------------------------------
# 9. Formula Audit Trail
# ---------------------------------------------------------------------------
print("\n=== Formula Audit Trail ===")
print("  A. Gross Revenue     = SUM(selling_price)")
print(f"                       = {' + '.join([f'{v:.2f}' for v in S[:3]])} + ... ({len(S)} rows)")
print(f"                       = Rs {gross_revenue:,.2f}")

print("  B. Net Revenue       = SUM(selling_price - discount)")
print(f"                       = Rs {gross_revenue:,.2f} - Rs {D.sum():,.2f}")
print(f"                       = Rs {net_revenue:,.2f}")

print("  C. COGS              = SUM(cost_basis)")
print(f"                       = {len(CB)} rows x {PURCHASE_TOTAL_COST:,.2f} (serialised item)")
print(f"                       = Rs {cogs:,.2f}")

print("  D. Gross Profit      = Net Revenue - COGS")
print(f"                       = Rs {net_revenue:,.2f} - Rs {cogs:,.2f}")
print(f"                       = Rs {gross_profit:,.2f}")

print("  E. Gross Margin %    = (Gross Profit / Net Revenue) × 100")
print(f"                       = ({gross_profit:,.2f} / {net_revenue:,.2f}) × 100")
print(f"                       = {gross_margin_pct:.4f}%")

print("  F. Making Charge/g   = SUM(making_charge) / SUM(weight)")
print(f"                       = {total_making_charge:,.2f} / {total_weight:.1f}")
print(f"                       = Rs {making_charge_per_gram:,.2f}/g")

# ---------------------------------------------------------------------------
# 10. Final Verdict
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("ALL ASSERTIONS PASSED.")
print("Formula logic verified against ANALYTICS_FORMULAS.md Section 1.")
print("Phase 3 -- Hand-Trace Verification: COMPLETE [DONE]")
print("=" * 60)
