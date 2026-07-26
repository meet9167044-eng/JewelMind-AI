"""
Compute ground-truth Phase 9 values from the seeded MySQL data.
Runs against jewelmind_db, business_id = 1, June 2026 vs May 2026.
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pymysql
import pandas as pd

conn = pymysql.connect(host='localhost', user='root', password='Meet12', database='jewelmind_db')

def month_sales(year, month):
    df = pd.read_sql(f"""
        SELECT s.sale_id, s.weight, s.selling_price, s.discount,
               s.making_charge, s.cost_basis, p.category
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        WHERE s.business_id = 1
          AND YEAR(s.sale_date) = {year}
          AND MONTH(s.sale_date) = {month}
    """, conn)
    return df

may  = month_sales(2026, 5)
june = month_sales(2026, 6)

def metrics(df):
    if len(df) == 0:
        return dict(W=0, GP=0, disc_pg=0, mc_pg=0, cat={})
    W  = df['weight'].sum()
    net_rev = (df['selling_price'] - df['discount']).sum()
    cogs    = df['cost_basis'].sum()
    GP      = net_rev - cogs
    disc_pg = df['discount'].sum() / W if W > 0 else 0
    mc_pg   = df['making_charge'].sum() / W if W > 0 else 0
    margin_rate = GP / W if W > 0 else 0
    cat = {}
    for cat_name, grp in df.groupby('category'):
        w_c  = grp['weight'].sum()
        gp_c = ((grp['selling_price'] - grp['discount']) - grp['cost_basis']).sum()
        cat[cat_name] = {'W': w_c, 'GP': gp_c, 'margin_rate': gp_c / w_c if w_c > 0 else 0}
    return dict(W=W, GP=GP, disc_pg=disc_pg, mc_pg=mc_pg,
                margin_rate=margin_rate, cat=cat)

mA = metrics(may)
mB = metrics(june)

W_A = mA['W'];  W_B = mB['W']
GP_A = mA['GP']; GP_B = mB['GP']
margin_A = mA['margin_rate']

delta_GP   = GP_B - GP_A
delta_vol  = (W_B - W_A) * margin_A
delta_disc = -(mB['disc_pg'] - mA['disc_pg']) * W_B
delta_mc   = (mB['mc_pg'] - mA['mc_pg']) * W_B

# Mix effect
delta_mix = 0
all_cats = set(mA['cat'].keys()) | set(mB['cat'].keys())
for cat in all_cats:
    wBc = mB['cat'].get(cat, {}).get('W', 0)
    wAc = mA['cat'].get(cat, {}).get('W', 0)
    mrAc = mA['cat'].get(cat, {}).get('margin_rate', 0)
    if W_B > 0 and W_A > 0:
        delta_mix += (wBc/W_B - wAc/W_A) * W_B * mrAc

delta_metal = delta_GP - (delta_vol + delta_disc + delta_mc + delta_mix)

print(f"=== Phase 9 Ground Truth (June 2026 vs May 2026, business_id=1) ===")
print(f"May  rows  : {len(may):,}  | W_A = {W_A:,.2f}g | GP_A = ₹{GP_A:,.2f}")
print(f"June rows  : {len(june):,}  | W_B = {W_B:,.2f}g | GP_B = ₹{GP_B:,.2f}")
print(f"")
print(f"delta_GP    = ₹{delta_GP:>12,.2f}")
print(f"delta_vol   = ₹{delta_vol:>12,.2f}")
print(f"delta_disc  = ₹{delta_disc:>12,.2f}")
print(f"delta_mc    = ₹{delta_mc:>12,.2f}")
print(f"delta_mix   = ₹{delta_mix:>12,.2f}")
print(f"delta_metal = ₹{delta_metal:>12,.2f}")
print(f"")
check = delta_vol + delta_disc + delta_mc + delta_mix + delta_metal
print(f"Sum of drivers = ₹{check:,.2f}  (must equal delta_GP = ₹{delta_GP:,.2f})")
print(f"Additive check: {'PASS' if abs(check - delta_GP) < 0.01 else 'FAIL'}")
conn.close()
