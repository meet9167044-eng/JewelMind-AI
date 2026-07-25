"""
Phase 2 Verification Script — JewelMind-AI
Verifies the 4 generated CSVs against the expected schema and scenarios.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import os

DATA = "data"
products  = pd.read_csv(os.path.join(DATA, "products.csv"))
purchases = pd.read_csv(os.path.join(DATA, "purchases.csv"))
sales     = pd.read_csv(os.path.join(DATA, "sales.csv"))
rates     = pd.read_csv(os.path.join(DATA, "metal_rates.csv"))

print("=== CSV Column Verification ===")
print("products columns :", list(products.columns))
print("purchases columns:", list(purchases.columns))
print("sales columns    :", list(sales.columns))
print("rates columns    :", list(rates.columns))

print("\n=== Row Counts ===")
print(f"products  : {len(products):>6,}")
print(f"purchases : {len(purchases):>6,}")
print(f"sales     : {len(sales):>6,}")
print(f"rates     : {len(rates):>6,}")

print("\n=== Scenario A Verification (June Profit Drop) ===")
sales["month"] = pd.to_datetime(sales["sale_date"]).dt.month
may_sales  = sales[sales["month"] == 5]
june_sales = sales[sales["month"] == 6]
print(f"May  sales : {len(may_sales):>4}  rows  |  total weight: {may_sales['weight'].sum():,.1f}g")
print(f"June sales : {len(june_sales):>4}  rows  |  total weight: {june_sales['weight'].sum():,.1f}g")
vol_chg = (june_sales["weight"].sum() - may_sales["weight"].sum()) / may_sales["weight"].sum() * 100
print(f"Volume change May->June : {vol_chg:+.1f}%")

may_disc  = (may_sales["discount"]  / may_sales["selling_price"]).mean() * 100
june_disc = (june_sales["discount"] / june_sales["selling_price"]).mean() * 100
print(f"Avg discount rate   May : {may_disc:.2f}%    June: {june_disc:.2f}%    change: {june_disc - may_disc:+.2f}pp")

may_mc  = (may_sales["making_charge"]  / may_sales["weight"]).mean()
june_mc = (june_sales["making_charge"] / june_sales["weight"]).mean()
mc_chg  = (june_mc - may_mc) / may_mc * 100
print(f"Avg MC/gram         May : Rs{may_mc:.0f}     June: Rs{june_mc:.0f}     change: {mc_chg:+.1f}%")

print("\n=== Scenario B Verification (July Silver Fall) ===")
jun30 = rates[rates["rate_date"] == "2026-06-30"]["silver"].values[0]
jul01 = rates[rates["rate_date"] == "2026-07-01"]["silver"].values[0]
print(f"Silver Jun-30 : Rs{jun30}  Jul-01 : Rs{jul01}  drop: {(jul01 - jun30) / jun30 * 100:+.1f}%")

print("\n=== Constraint Checks (all should be False/True) ===")
print(f"Any negative selling_price?              {(sales['selling_price'] < 0).any()}")
print(f"Any negative discount?                   {(sales['discount'] < 0).any()}")
print(f"Any net_weight > gross_weight?           {(products['net_weight'] > products['gross_weight']).any()}")
print(f"All purchase total_cost > 0?             {(purchases['total_cost'] > 0).all()}")
print(f"All category values valid?               {products['category'].isin(['chain','necklace','payal','coin','utensil','ring','bangle','earring']).all()}")
print(f"All metal values valid?                  {products['metal'].isin(['gold','silver']).all()}")

print("\nVerification complete.")
