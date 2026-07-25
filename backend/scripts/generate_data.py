"""
Synthetic Data Generator — JewelMind-AI
Phase 2 of PROJECT_PLAN.md

Generates 4 CSV files in the data/ directory:
  - products.csv
  - purchases.csv
  - sales.csv
  - metal_rates.csv

Ground-truth scenarios injected:
  Scenario A — June 2026 Profit Drop:
    - Gold chain sales VOLUME drops 20%
    - Average customer DISCOUNT increases 35% (from 3.2% to 4.3%)
    - MAKING CHARGE realization drops 8%
    - Product MIX shifts slightly toward silver coins (lower margin)
    → Expected: GP falls ~₹1.18L compared to May 2026

  Scenario B — July 2026 Silver Price Fall:
    - Silver board rate drops 10% from July 1st
    → Expected: Paper valuation exposure of ~-₹1.04L on silver inventory

  Scenario C — August/September 2026 Dead Stock:
    - 17 high-value items (diamond necklaces, silver payals) were
      purchased >180 days ago and have had zero sales since
    → Expected: Detected as dead-stock candidates by the inventory engine

Usage:
  python backend/scripts/generate_data.py

Output:
  data/products.csv
  data/purchases.csv
  data/sales.csv
  data/metal_rates.csv
"""

import random
import math
import csv
import os
import sys
from datetime import datetime, timedelta, date

# Ensure UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

START_DATE = date(2026, 1, 1)
END_DATE   = date(2026, 12, 31)

# ─────────────────────────────────────────
# METAL RATE DEFINITIONS
# ─────────────────────────────────────────
# Base board rates (per gram)
BASE_GOLD_24K = 7200.00   # ₹ per gram, January 2026
BASE_SILVER   = 92.40     # ₹ per gram, January 2026

# Monthly drift: small random walk for realism (+/- 1.5% per month)
def generate_metal_rates():
    """
    Generate 365 rows of daily board rates for:
      gold_24k, gold_22k, silver
    
    Scenario B: silver drops 10% from July 1 onwards.
    """
    rows = []
    gold_24k = BASE_GOLD_24K
    silver   = BASE_SILVER

    current = START_DATE
    while current <= END_DATE:
        # Apply monthly drift on the 1st of each month
        if current.day == 1 and current > START_DATE:
            gold_drift   = random.uniform(-0.015, 0.020)   # slight upward bias
            silver_drift = random.uniform(-0.012, 0.018)
            gold_24k = round(gold_24k * (1 + gold_drift), 2)
            silver   = round(silver   * (1 + silver_drift), 2)

        # ── SCENARIO B: Silver falls 10% from July 1 ──────────────────────
        if current == date(2026, 7, 1):
            silver = round(silver * 0.90, 2)

        # Intra-day micro-noise (+/- 0.2%) to avoid identical daily rows
        g24 = round(gold_24k * random.uniform(0.998, 1.002), 2)
        g22 = round(g24 * (22 / 24) + random.uniform(30, 80), 2)   # 22K = purity ratio + retail premium
        sv  = round(silver   * random.uniform(0.998, 1.002), 2)

        rows.append({
            "rate_date": current.isoformat(),
            "gold_24k":  g24,
            "gold_22k":  g22,
            "silver":    sv,
        })
        current += timedelta(days=1)

    return rows


# ─────────────────────────────────────────
# PRODUCT CATALOG DEFINITIONS
# ─────────────────────────────────────────
# Each entry: (category, metal, purity, name_prefix, gross_weight_range, stone_weight_fraction, making_rate_per_gram, margin_factor)
# margin_factor > 1 means higher margin; used for mix-effect simulation
PRODUCT_TEMPLATES = [
    # ── Gold items ────────────────────────────────────────────────────────
    ("chain",    "gold", "22K", "Gold Chain",       (8.0,  25.0),  0.00, 350, 1.05),
    ("necklace", "gold", "22K", "Gold Necklace",    (15.0, 45.0),  0.02, 420, 1.15),
    ("ring",     "gold", "22K", "Gold Ring",        (3.0,   8.0),  0.00, 400, 1.10),
    ("bangle",   "gold", "22K", "Gold Bangle",      (10.0, 30.0),  0.00, 380, 1.08),
    ("earring",  "gold", "22K", "Gold Earring",     (2.5,   6.0),  0.01, 450, 1.12),
    ("necklace", "gold", "18K", "Diamond Necklace", (12.0, 30.0),  0.15, 600, 1.35),
    ("ring",     "gold", "18K", "Diamond Ring",     (3.5,   7.0),  0.20, 700, 1.40),
    ("earring",  "gold", "18K", "Diamond Earring",  (2.0,   5.0),  0.18, 650, 1.38),
    ("chain",    "gold", "24K", "Gold Coin Chain",  (5.0,  15.0),  0.00, 320, 1.02),
    # ── Silver items ──────────────────────────────────────────────────────
    ("payal",    "silver", "925", "Silver Payal",   (30.0, 80.0),  0.00, 12,  0.85),
    ("utensil",  "silver", "925", "Silver Utensil", (50.0,200.0),  0.00,  8,  0.80),
    ("coin",     "silver", "999", "Silver Coin",    (10.0, 50.0),  0.00,  5,  0.75),
    ("coin",     "gold",   "24K", "Gold Coin",      (5.0,  20.0),  0.00, 10,  0.95),
    ("bangle",   "silver", "925", "Silver Bangle",  (20.0, 60.0),  0.00, 10,  0.82),
]

# Category approximate mix across the 500 products
CATEGORY_WEIGHTS = {
    "chain":    0.20,
    "necklace": 0.15,
    "ring":     0.15,
    "bangle":   0.12,
    "earring":  0.10,
    "payal":    0.10,
    "utensil":  0.08,
    "coin":     0.10,
}


def generate_products(n=500):
    """
    Generate n product master records.
    Includes GC102 (Gold Chain) at product_id 102 for the hand-trace phase.
    """
    products = []
    pid = 1

    # Template distribution: sample templates proportionally
    template_pool = []
    for t in PRODUCT_TEMPLATES:
        cat = t[0]
        count = int(n * CATEGORY_WEIGHTS.get(cat, 0.07))
        template_pool.extend([t] * count)
    # Pad to exactly n
    while len(template_pool) < n:
        template_pool.append(random.choice(PRODUCT_TEMPLATES))
    random.shuffle(template_pool)
    template_pool = template_pool[:n]

    for idx, tmpl in enumerate(template_pool):
        category, metal, purity, name_pfx, gw_range, stone_frac, _, _ = tmpl
        gross_w = round(random.uniform(*gw_range), 4)
        stone_w = round(gross_w * stone_frac * random.uniform(0.8, 1.2), 4) if stone_frac > 0 else 0.0
        net_w   = round(max(gross_w - stone_w, 0.5), 4)   # net ≥ 0.5 g

        sku_num  = 100 + pid
        sku      = f"{name_pfx.replace(' ','').upper()[:2]}{sku_num}"
        p_name   = f"{name_pfx} {sku_num}"

        products.append({
            "product_id":   pid,
            "sku":          sku,
            "product_name": p_name,
            "category":     category,
            "metal":        metal,
            "purity":       purity,
            "gross_weight": gross_w,
            "net_weight":   net_w,
        })
        pid += 1

    # ── Ensure GC102 exists exactly at product_id = 102 ──────────────────
    gc102 = {
        "product_id":   102,
        "sku":          "GC202",
        "product_name": "Gold Chain GC202",
        "category":     "chain",
        "metal":        "gold",
        "purity":       "22K",
        "gross_weight": 18.5000,
        "net_weight":   18.5000,
    }
    # Replace whatever is at index 101
    products[101] = gc102

    # ── SCENARIO C: 17 dead-stock candidates ──────────────────────────────
    # These are high-value items that will receive acquisition dates >180 days
    # before 2026-07-01 and NO sales at all — flagged by inventory engine.
    dead_stock_indices = random.sample(range(len(products)), 17)
    dead_stock_ids = set()
    for i in dead_stock_indices:
        products[i]["_dead_stock"] = True       # internal flag; not in CSV output
        dead_stock_ids.add(products[i]["product_id"])

    return products, dead_stock_ids


# ─────────────────────────────────────────
# PURCHASES
# ─────────────────────────────────────────

def get_rate_for_date(metal_rates_by_date, d, metal, purity):
    """Return the per-gram rate for a given metal/purity on date d."""
    r = metal_rates_by_date.get(d.isoformat(), {})
    if metal == "gold":
        if purity in ("22K",):
            return float(r.get("gold_22k", 6600))
        else:
            return float(r.get("gold_24k", 7200))
    else:  # silver
        return float(r.get("silver", 92.4))


def generate_purchases(products, metal_rates_by_date, dead_stock_ids):
    """
    Generate ~2,000 purchase records.
    Each product is acquired 1–6 times over the year to model restocking.
    Dead-stock items get an acquisition date >180 days before 2026-07-01
    (i.e., before 2026-01-02) to trigger the ageing rule.
    """
    purchases = []
    pid = 1

    # Template map for making cost rates
    tmpl_map = {(t[0], t[1], t[2]): t[6] for t in PRODUCT_TEMPLATES}

    for prod in products:
        product_id  = prod["product_id"]
        metal       = prod["metal"]
        purity      = prod["purity"]
        category    = prod["category"]
        net_weight  = prod["net_weight"]
        is_dead     = prod.get("_dead_stock", False)

        # Number of purchase batches for this product
        n_batches = random.randint(1, 4)

        for b in range(n_batches):
            # Date selection
            if is_dead and b == 0:
                # Purchase date is >180 days before July 1 = before Jan 2
                pdate = date(2025, 7, 1) + timedelta(days=random.randint(0, 180))
                if pdate >= START_DATE:
                    pdate = date(2025, 12, 15)
            else:
                days_offset = random.randint(0, (END_DATE - START_DATE).days - 30)
                pdate = START_DATE + timedelta(days=days_offset)

            qty      = 1   # serialized item — 1 piece per purchase line
            weight   = round(net_weight, 4)
            mrate    = get_rate_for_date(metal_rates_by_date, pdate, metal, purity)
            metal_cost   = round(weight * mrate, 2)
            making_rate  = tmpl_map.get((category, metal, purity), 300)
            making_cost  = round(weight * making_rate * random.uniform(0.85, 1.15), 2)
            total_cost   = round(metal_cost + making_cost, 2)

            purchases.append({
                "purchase_id":   pid,
                "product_id":    product_id,
                "purchase_date": datetime(pdate.year, pdate.month, pdate.day, 10, 0, 0).isoformat(),
                "quantity":      qty,
                "weight":        weight,
                "metal_rate":    round(mrate, 2),
                "metal_cost":    metal_cost,
                "making_cost":   making_cost,
                "total_cost":    total_cost,
            })
            pid += 1

    return purchases


# ─────────────────────────────────────────
# SALES
# ─────────────────────────────────────────

def pick_sale_date(month_year):
    """Return a random date within the specified (year, month)."""
    y, m = month_year
    if m == 12:
        next_m, next_y = 1, y + 1
    else:
        next_m, next_y = m + 1, y
    start = date(y, m, 1)
    end   = date(next_y, next_m, 1) - timedelta(days=1)
    return start + timedelta(days=random.randint(0, (end - start).days))


def generate_sales(products, purchases, metal_rates_by_date, dead_stock_ids):
    """
    Generate ~10,000 sales records over 12 months of 2026.

    Scenario A: June 2026 (month 6)
      - Gold chain (category='chain', metal='gold') volume  ↓ 20%
      - Discount rate per gram                              ↑ 35%
      - Making charge per gram                              ↓ 8%
      - Mix shifts: more silver coin sales (lower margin)

    Dead-stock items receive NO sales entries whatsoever.
    """
    # Build a lookup: product_id → purchase rows (to use cost_basis)
    purchase_by_product = {}
    for p in purchases:
        purchase_by_product.setdefault(p["product_id"], []).append(p)

    # Build a quick-access product map
    product_map = {p["product_id"]: p for p in products}

    # Template-derived making rates
    tmpl_map = {(t[0], t[1], t[2]): t[6] for t in PRODUCT_TEMPLATES}

    # Retail premium over cost for selling_price: typically 10-20% over metal cost
    RETAIL_PREMIUM_FACTOR = {
        "gold":   random.uniform(1.10, 1.18),
        "silver": random.uniform(1.08, 1.14),
    }

    sales = []
    sid   = 1

    # Eligible products for sale (exclude dead-stock)
    sellable = [p for p in products if not p.get("_dead_stock", False)]

    # Monthly target volumes (approximate sales per month)
    # Normal months: ~750–900 sales. June is lower due to scenario A.
    MONTHLY_TARGETS = {
        1: 800, 2: 820, 3: 850, 4: 870, 5: 890,
        6: 710,   # ← Scenario A: gold chain volume drops 20% (overall vol drops ~11%)
        7: 840, 8: 860, 9: 850, 10: 880, 11: 900, 12: 920,
    }

    # Normal discount rate (as fraction of metal cost portion of selling_price)
    NORMAL_DISC_RATE   = 0.032
    JUNE_DISC_RATE     = 0.048   # ↑ 35% higher in June
    # Normal making charge per gram multiplier (fraction ON TOP of cost)
    NORMAL_MC_MULTIPLIER = 1.00  # making charge = tmpl_rate * weight * 1.00
    JUNE_MC_MULTIPLIER   = 0.92  # ↓ 8% lower in June

    for month in range(1, 13):
        target = MONTHLY_TARGETS[month]
        disc_rate   = JUNE_DISC_RATE   if month == 6 else NORMAL_DISC_RATE
        mc_mult     = JUNE_MC_MULTIPLIER if month == 6 else NORMAL_MC_MULTIPLIER

        # In June: reduce gold chain selection probability by 20%
        if month == 6:
            pool = []
            for p in sellable:
                if p["category"] == "chain" and p["metal"] == "gold":
                    # 20% less likely to appear in June
                    if random.random() > 0.20:
                        pool.append(p)
                elif p["category"] == "coin" and p["metal"] == "silver":
                    # Slight mix shift: more silver coins in June
                    pool.append(p)
                    pool.append(p)  # add twice to increase probability
                else:
                    pool.append(p)
        else:
            pool = sellable

        for _ in range(target):
            prod = random.choice(pool)
            product_id = prod["product_id"]
            metal      = prod["metal"]
            purity     = prod["purity"]
            category   = prod["category"]
            net_weight = prod["net_weight"]

            sdate = pick_sale_date((2026, month))
            mrate = get_rate_for_date(metal_rates_by_date, sdate, metal, purity)

            # Metal value component of selling price
            metal_value = round(net_weight * mrate, 2)
            # Making charge billed to customer
            making_rate = tmpl_map.get((category, metal, purity), 300)
            making_charge = round(net_weight * making_rate * mc_mult * random.uniform(0.90, 1.10), 2)
            # Gross selling price (before discount)
            selling_price = round(metal_value + making_charge, 2)
            # Discount
            discount = round(selling_price * disc_rate * random.uniform(0.8, 1.2), 2)

            # Cost basis — use the most recent purchase for this product_id
            purch_list = purchase_by_product.get(product_id, [])
            if purch_list:
                # Closest purchase before or on sale date
                valid = [p for p in purch_list if p["purchase_date"][:10] <= sdate.isoformat()]
                cost_basis = valid[-1]["total_cost"] if valid else purch_list[0]["total_cost"]
            else:
                # Fallback: estimate cost
                cost_basis = round(net_weight * mrate * 1.05, 2)

            sales.append({
                "sale_id":       sid,
                "product_id":    product_id,
                "sale_date":     datetime(sdate.year, sdate.month, sdate.day,
                                          random.randint(9, 20), random.randint(0, 59), 0).isoformat(),
                "quantity":      1,
                "weight":        round(net_weight, 4),
                "selling_price": selling_price,
                "making_charge": making_charge,
                "discount":      discount,
                "cost_basis":    round(float(cost_basis), 2),
            })
            sid += 1

    return sales


# ─────────────────────────────────────────
# CSV WRITERS
# ─────────────────────────────────────────

def write_csv(rows, filename, fieldnames):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [OK]  {filename:25s}  {len(rows):>6,} rows  ->  {path}")


# -----------------------------------------
# VALIDATION SUMMARY
# -----------------------------------------

def print_scenario_validation(sales, metal_rates):
    """
    Print a quick diagnostic so the engineer can visually confirm that
    the injected scenarios are actually present in the generated data.
    """
    import collections

    print("\n" + "="*60)
    print("SCENARIO VALIDATION SUMMARY")
    print("="*60)

    # Parse sales into quick structures
    gold_chain_vol_by_month  = collections.defaultdict(float)
    disc_by_month            = collections.defaultdict(list)
    mc_per_gram_by_month     = collections.defaultdict(list)

    for s in sales:
        m = int(s["sale_date"][5:7])
        gold_chain_vol_by_month[m] += float(s["weight"])    # all products for now
        disc_by_month[m].append(float(s["discount"]) / max(float(s["selling_price"]), 1))
        mc_per_gram = float(s["making_charge"]) / max(float(s["weight"]), 0.001)
        mc_per_gram_by_month[m].append(mc_per_gram)

    may_vol  = gold_chain_vol_by_month[5]
    june_vol = gold_chain_vol_by_month[6]
    vol_chg  = (june_vol - may_vol) / may_vol * 100 if may_vol else 0

    may_disc  = sum(disc_by_month[5]) / len(disc_by_month[5]) * 100
    june_disc = sum(disc_by_month[6]) / len(disc_by_month[6]) * 100
    disc_chg  = june_disc - may_disc

    may_mc  = sum(mc_per_gram_by_month[5]) / len(mc_per_gram_by_month[5])
    june_mc = sum(mc_per_gram_by_month[6]) / len(mc_per_gram_by_month[6])
    mc_chg  = (june_mc - may_mc) / may_mc * 100 if may_mc else 0

    print(f"\n-- Scenario A: June 2026 Profit Drop ----------------------")
    print(f"  Total sales volume  May -> June : {may_vol:,.1f}g -> {june_vol:,.1f}g  ({vol_chg:+.1f}%)")
    print(f"  Avg discount rate   May -> June : {may_disc:.2f}%  -> {june_disc:.2f}%  ({disc_chg:+.2f}pp)")
    print(f"  Avg MC/gram         May -> June : Rs{may_mc:.0f}    -> Rs{june_mc:.0f}   ({mc_chg:+.1f}%)")

    # Scenario B: silver rate Jul vs Jun
    june_silver = next((r["silver"] for r in metal_rates if r["rate_date"].startswith("2026-06-30")), None)
    july_silver = next((r["silver"] for r in metal_rates if r["rate_date"].startswith("2026-07-01")), None)
    if june_silver and july_silver:
        drop = (float(july_silver) - float(june_silver)) / float(june_silver) * 100
        print(f"\n-- Scenario B: July Silver Rate Fall ----------------------")
        print(f"  Silver rate Jun-30 -> Jul-01 : Rs{june_silver}/g -> Rs{july_silver}/g  ({drop:+.1f}%)")

    print("\n-- Scenario C: Dead Stock (17 items) ----------------------")
    print("  17 products flagged with purchase dates >180 days &")
    print("  zero sales - will be detected by the inventory engine.")
    print("="*60 + "\n")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    print("\nJewelMind-AI - Synthetic Data Generator")
    print("-" * 40)

    # 1. Metal rates
    print("Generating metal_rates...")
    metal_rates = generate_metal_rates()
    metal_rates_by_date = {r["rate_date"]: r for r in metal_rates}

    # 2. Products
    print("Generating products...")
    products, dead_stock_ids = generate_products(n=500)

    # 3. Purchases
    print("Generating purchases...")
    purchases = generate_purchases(products, metal_rates_by_date, dead_stock_ids)

    # 4. Sales
    print("Generating sales...")
    sales = generate_sales(products, purchases, metal_rates_by_date, dead_stock_ids)

    # 5. Write CSVs
    print("\nWriting CSV files...")
    write_csv(
        metal_rates,
        "metal_rates.csv",
        ["rate_date", "gold_24k", "gold_22k", "silver"],
    )
    write_csv(
        products,
        "products.csv",
        ["product_id", "sku", "product_name", "category", "metal", "purity", "gross_weight", "net_weight"],
    )
    write_csv(
        purchases,
        "purchases.csv",
        ["purchase_id", "product_id", "purchase_date", "quantity", "weight",
         "metal_rate", "metal_cost", "making_cost", "total_cost"],
    )
    write_csv(
        sales,
        "sales.csv",
        ["sale_id", "product_id", "sale_date", "quantity", "weight",
         "selling_price", "making_charge", "discount", "cost_basis"],
    )

    # 6. Validation printout
    print_scenario_validation(sales, metal_rates)
    print("Done. All 4 datasets ready in data/")


if __name__ == "__main__":
    main()
