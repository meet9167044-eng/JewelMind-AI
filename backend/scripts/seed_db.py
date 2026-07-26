"""
backend/scripts/seed_db.py — Development Database Seeder
=========================================================
Seeds the JewelMind-AI MySQL database with:

  1. Demo user   : demo@jewelmind.com  /  demo123
  2. Demo business: "Rajesh Jewellers Demo"  (owned by demo user)
  3. Products    : data/products.csv   → all rows tagged business_id=1
  4. Purchases   : data/purchases.csv  → all rows tagged business_id=1
  5. Sales       : data/sales.csv      → all rows tagged business_id=1
  6. Metal rates : data/metal_rates.csv → global reference table (DEV fixture only)

IMPORTANT — Development vs Production:
    metal_rates.csv is ONLY used here for local development and demo seeding.
    In production, the Metal Rate Fetch Service populates metal_rates
    automatically. Never upload metal_rates.csv in production.

Run:
    python backend/scripts/seed_db.py

The script is idempotent for the demo user and business — re-running
does not create duplicates. CSV data is cleared and reloaded on each run
so the demo database always reflects the current CSV files.
"""

import pathlib
import sys
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.database import SessionLocal, engine, Base  # noqa: E402
from backend.app.models import (  # noqa: E402
    business,
    metal_rate,
    product,
    purchase,
    sale,
    user,
)
from backend.app.services.auth_service import hash_password

DATA = ROOT / "data"

DEMO_EMAIL    = "demo@jewelmind.com"
DEMO_PASSWORD = "demo123"
DEMO_BUSINESS = "Rajesh Jewellers Demo"
BUSINESS_ID   = 1   # The seed always assigns business_id = 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_demo_user(db: Session) -> user.User:
    existing = db.query(user.User).filter(user.User.email == DEMO_EMAIL).first()
    if existing:
        print(f"  Demo user already exists (user_id={existing.user_id})")
        return existing
    u = user.User(
        email=DEMO_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name="Demo Owner",
    )
    db.add(u)
    db.flush()
    print(f"  Created demo user (user_id={u.user_id})")
    return u


def _get_or_create_demo_business(db: Session, owner_user_id: int) -> business.Business:
    existing = (
        db.query(business.Business)
        .filter(business.Business.business_name == DEMO_BUSINESS)
        .first()
    )
    if existing:
        print(f"  Demo business already exists (business_id={existing.business_id})")
        return existing
    b = business.Business(
        owner_user_id=owner_user_id,
        business_name=DEMO_BUSINESS,
        owner_name="Rajesh Mehta",
        email="demo@rajeshjewellers.in",
        phone="+91-9876543210",
    )
    db.add(b)
    db.flush()
    print(f"  Created demo business (business_id={b.business_id})")
    return b


def _seed_products(db: Session, demo_business_id: int) -> dict[int, int]:
    """
    Seed products.csv into the products table.
    Returns a mapping: {csv_product_id → db_product_id}
    (IDs may differ if data was seeded before with different auto-increment state)
    """
    # Clear existing products for this business
    db.query(product.Product).filter(
        product.Product.business_id == demo_business_id
    ).delete(synchronize_session=False)
    db.flush()

    df = pd.read_csv(DATA / "products.csv")
    id_map: dict[int, int] = {}
    rows = []
    for _, row in df.iterrows():
        p = product.Product(
            business_id=demo_business_id,
            sku=str(row["sku"]),
            product_name=str(row["product_name"]),
            category=str(row["category"]),
            metal=str(row["metal"]),
            purity=str(row["purity"]),
            gross_weight=float(row["gross_weight"]),
            net_weight=float(row["net_weight"]),
        )
        db.add(p)
        rows.append((int(row["product_id"]), p))
    db.flush()
    for csv_id, p in rows:
        id_map[csv_id] = p.product_id
    print(f"  Seeded {len(rows):,} products")
    return id_map


def _seed_purchases(db: Session, demo_business_id: int, id_map: dict[int, int]) -> None:
    db.query(purchase.Purchase).filter(
        purchase.Purchase.business_id == demo_business_id
    ).delete(synchronize_session=False)
    db.flush()

    df = pd.read_csv(DATA / "purchases.csv")
    count = 0
    for _, row in df.iterrows():
        csv_pid = int(row["product_id"])
        db_pid = id_map.get(csv_pid)
        if db_pid is None:
            continue   # skip orphaned rows (shouldn't happen)
        p = purchase.Purchase(
            business_id=demo_business_id,
            product_id=db_pid,
            purchase_date=datetime.fromisoformat(str(row["purchase_date"])),
            quantity=int(row["quantity"]),
            weight=float(row["weight"]),
            metal_rate=float(row["metal_rate"]),
            metal_cost=float(row["metal_cost"]),
            making_cost=float(row["making_cost"]),
            total_cost=float(row["total_cost"]),
        )
        db.add(p)
        count += 1
    db.flush()
    print(f"  Seeded {count:,} purchases")


def _seed_sales(db: Session, demo_business_id: int, id_map: dict[int, int]) -> None:
    db.query(sale.Sale).filter(
        sale.Sale.business_id == demo_business_id
    ).delete(synchronize_session=False)
    db.flush()

    df = pd.read_csv(DATA / "sales.csv")
    count = 0
    for _, row in df.iterrows():
        csv_pid = int(row["product_id"])
        db_pid = id_map.get(csv_pid)
        if db_pid is None:
            continue
        s = sale.Sale(
            business_id=demo_business_id,
            product_id=db_pid,
            sale_date=datetime.fromisoformat(str(row["sale_date"])),
            quantity=int(row["quantity"]),
            weight=float(row["weight"]),
            selling_price=float(row["selling_price"]),
            making_charge=float(row["making_charge"]),
            discount=float(row["discount"]),
            cost_basis=float(row["cost_basis"]),
        )
        db.add(s)
        count += 1
    db.flush()
    print(f"  Seeded {count:,} sales")


def _seed_metal_rates(db: Session) -> None:
    """
    DEV FIXTURE ONLY — loads metal_rates.csv into the global metal_rates table.
    In production this table is populated by the Metal Rate Fetch Service.
    """
    # Remove existing rows (upsert-style: clear + reload)
    db.query(metal_rate.MetalRate).delete(synchronize_session=False)
    db.flush()

    df = pd.read_csv(DATA / "metal_rates.csv")
    for _, row in df.iterrows():
        mr = metal_rate.MetalRate(
            rate_date=pd.to_datetime(row["rate_date"]).date(),
            gold_24k=float(row["gold_24k"]),
            gold_22k=float(row["gold_22k"]),
            silver=float(row["silver"]),
        )
        db.add(mr)
    db.flush()
    print(f"  Seeded {len(df):,} metal rate rows (DEV fixture)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("JewelMind-AI — Development Database Seeder")
    print("=" * 60)

    db: Session = SessionLocal()
    try:
        print("\n[1/6] Demo user ...")
        demo_user = _get_or_create_demo_user(db)

        print("\n[2/6] Demo business ...")
        demo_biz = _get_or_create_demo_business(db, demo_user.user_id)

        print("\n[3/6] Products ...")
        id_map = _seed_products(db, demo_biz.business_id)

        print("\n[4/6] Purchases ...")
        _seed_purchases(db, demo_biz.business_id, id_map)

        print("\n[5/6] Sales ...")
        _seed_sales(db, demo_biz.business_id, id_map)

        print("\n[6/6] Metal rates (DEV fixture only) ...")
        _seed_metal_rates(db)

        db.commit()
        print("\n" + "=" * 60)
        print("Seeding complete.")
        print(f"  Demo login  : {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"  Business ID : {demo_biz.business_id}")
        print("=" * 60)

    except Exception as exc:
        db.rollback()
        print(f"\nERROR: Seeding failed — {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
