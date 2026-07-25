# DATABASE_SCHEMA.md

## Status

This document defines the schema for the **JewelMind-AI** multi-business SaaS platform. All tables that contain business data are scoped to a `business_id` foreign key. A query that aggregates across businesses without a `business_id` filter is a critical data-isolation bug (see PROJECT_RULES.md, rule 11).

## Database Technology

*   **Database**: PostgreSQL (v14+)
*   **Access Layer**: SQLAlchemy ORM (v2.0+) using declarative mapping
*   **Migrations**: Alembic

---

## 1. Full Entity Relationship Diagram

```
┌──────────────────────┐        ┌──────────────────────────┐
│         users        │        │        businesses         │
├──────────────────────┤        ├──────────────────────────┤
│ PK user_id (INT)     │──┐     │ PK business_id (INT)     │
│    email (VARCHAR)   │  │     │ FK owner_user_id (INT)──►│ users
│    password_hash     │  └────►│    business_name (VAR)   │
│    full_name (VAR)   │        │    owner_name (VAR)      │
│    created_at (TS)   │        │    email (VARCHAR)        │
│    updated_at (TS)   │        │    phone (VARCHAR)        │
└──────────────────────┘        │    created_at (TS)        │
                                │    updated_at (TS)        │
                                └────────────┬─────────────┘
                                             │ business_id FK (all tables below)
             ┌───────────────────────────────┼───────────────────────────────┐
             ▼                               ▼                               ▼
┌───────────────────────┐     ┌─────────────────────────┐    ┌─────────────────────────┐
│       products        │     │        purchases         │    │          sales          │
├───────────────────────┤     ├─────────────────────────┤    ├─────────────────────────┤
│ PK product_id (INT)   │◄────│ FK product_id (INT)     │    │ FK product_id (INT)    ◄┐
│ FK business_id (INT)  │     │ FK business_id (INT)    │    │ FK business_id (INT)    │
│    sku (VARCHAR)      │     │ PK purchase_id (INT)    │    │ PK sale_id (INT)        │
│    product_name (VAR) │     │    purchase_date (TS)   │    │    sale_date (TS)       │
│    category (VAR)     │     │    quantity (INT)       │    │    quantity (INT)       │
│    metal (VARCHAR)    │     │    weight (DEC)         │    │    weight (DEC)         │
│    purity (VARCHAR)   │     │    metal_rate (DEC)     │    │    selling_price (DEC)  │
│    gross_weight (DEC) │     │    metal_cost (DEC)     │    │    making_charge (DEC)  │
│    net_weight (DEC)   │     │    making_cost (DEC)    │    │    discount (DEC)       │
└───────────────────────┘     │    total_cost (DEC)     │    │    cost_basis (DEC)     │
                              └─────────────────────────┘    └─────────────────────────┘

┌────────────────────────────┐
│        metal_rates         │
├────────────────────────────┤
│ FK business_id (INT)       │◄── (Composite PK: business_id + rate_date)
│ PK rate_date (DATE)        │
│    gold_24k (DECIMAL)      │
│    gold_22k (DECIMAL)      │
│    silver (DECIMAL)        │
└────────────────────────────┘
```

---

## 2. Table Definitions & Design Intent

### Table 1: `users`
Stores registered user accounts. Authentication is handled by hashing passwords here and issuing JWTs at login.

| Column | Type | Notes |
|---|---|---|
| user_id | SERIAL PRIMARY KEY | Auto-incremented |
| email | VARCHAR(255) UNIQUE NOT NULL | Login identity |
| password_hash | VARCHAR(512) NOT NULL | bcrypt hash; never store plaintext |
| full_name | VARCHAR(255) NOT NULL | Display name |
| created_at | TIMESTAMP WITH TIME ZONE | Auto-set on insert |
| updated_at | TIMESTAMP WITH TIME ZONE | Auto-updated |

---

### Table 2: `businesses`
Every registered user may own one or more named jewellery businesses. This table is the multi-tenancy anchor — every business-data table references `business_id` from here.

| Column | Type | Notes |
|---|---|---|
| business_id | SERIAL PRIMARY KEY | Multi-tenancy anchor key |
| owner_user_id | INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE | Who owns this business |
| business_name | VARCHAR(255) NOT NULL | e.g., "Rajesh Jewellers" |
| owner_name | VARCHAR(255) | Contact name within the business |
| email | VARCHAR(255) | Business contact email |
| phone | VARCHAR(50) | Business contact phone |
| created_at | TIMESTAMP WITH TIME ZONE | Auto-set on insert |
| updated_at | TIMESTAMP WITH TIME ZONE | Auto-updated |

---

### Table 3: `products`
Master catalogue for each jewellery item belonging to a specific business.

| Column | Type | Notes |
|---|---|---|
| product_id | SERIAL PRIMARY KEY | |
| business_id | INT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE | **Data isolation key** |
| sku | VARCHAR(100) NOT NULL | Unique *per business* (not globally) |
| product_name | VARCHAR(255) NOT NULL | |
| category | VARCHAR(100) NOT NULL | Enum: chain, necklace, payal, coin, utensil, ring, bangle, earring |
| metal | VARCHAR(50) NOT NULL | Enum: gold, silver |
| purity | VARCHAR(50) NOT NULL | e.g., 22K, 24K, 18K, 925 |
| gross_weight | NUMERIC(10, 4) NOT NULL | Total piece weight in grams |
| net_weight | NUMERIC(10, 4) NOT NULL | Metal-only weight in grams |

> Unique constraint: `(business_id, sku)` — the same SKU may exist in different businesses.

---

### Table 4: `purchases`
Inventory inflows for a specific business.

| Column | Type | Notes |
|---|---|---|
| purchase_id | SERIAL PRIMARY KEY | |
| business_id | INT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE | **Data isolation key** |
| product_id | INT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE | |
| purchase_date | TIMESTAMP WITH TIME ZONE NOT NULL | |
| quantity | INT NOT NULL | |
| weight | NUMERIC(10, 4) NOT NULL | |
| metal_rate | NUMERIC(12, 2) NOT NULL | Rate per gram at acquisition time |
| metal_cost | NUMERIC(12, 2) NOT NULL | |
| making_cost | NUMERIC(12, 2) NOT NULL | Labor paid to supplier/karigar |
| total_cost | NUMERIC(12, 2) NOT NULL | metal_cost + making_cost |

---

### Table 5: `sales`
Inventory outflows for a specific business. Price components are captured dynamically at billing time.

| Column | Type | Notes |
|---|---|---|
| sale_id | SERIAL PRIMARY KEY | |
| business_id | INT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE | **Data isolation key** |
| product_id | INT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE | |
| sale_date | TIMESTAMP WITH TIME ZONE NOT NULL | |
| quantity | INT NOT NULL | |
| weight | NUMERIC(10, 4) NOT NULL | |
| selling_price | NUMERIC(12, 2) NOT NULL | Gross price before discount |
| making_charge | NUMERIC(12, 2) NOT NULL | Labor billed to customer |
| discount | NUMERIC(12, 2) NOT NULL DEFAULT 0.00 | Deducted from selling price |
| cost_basis | NUMERIC(12, 2) NOT NULL | Derived from purchases.total_cost for accurate GP |

---

### Table 6: `metal_rates`
Daily commodity reference rates. Each business maintains its own rate history (uploaded with their data), ensuring no cross-business rate conflicts.

| Column | Type | Notes |
|---|---|---|
| business_id | INT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE | **Data isolation key** |
| rate_date | DATE NOT NULL | |
| gold_24k | NUMERIC(12, 2) NOT NULL | |
| gold_22k | NUMERIC(12, 2) NOT NULL | |
| silver | NUMERIC(12, 2) NOT NULL | |

> Primary Key: `(business_id, rate_date)` — composite key.

---

## 3. Key Relationships & Constraints

```
users (1) ──────────── (many) businesses
businesses (1) ──────── (many) products
businesses (1) ──────── (many) purchases
businesses (1) ──────── (many) sales
businesses (1) ──────── (many) metal_rates
products (1) ──────────── (many) purchases
products (1) ──────────── (many) sales
```

**SKU Uniqueness**: `(business_id, sku)` — unique per business, not globally.

**Rate Lookup**: When joining `sales` to `metal_rates` for valuation, always filter by both `business_id` AND `rate_date`.

---

## 4. Database Indexes

```sql
-- User/business resolution
CREATE INDEX idx_businesses_owner ON businesses(owner_user_id);

-- Analytics query performance (business-scoped)
CREATE INDEX idx_products_business ON products(business_id);
CREATE INDEX idx_products_metal_category ON products(business_id, metal, category);
CREATE INDEX idx_purchases_business_date ON purchases(business_id, purchase_date);
CREATE INDEX idx_sales_business_date ON sales(business_id, sale_date);
CREATE INDEX idx_sales_business_product ON sales(business_id, product_id);
CREATE INDEX idx_metal_rates_business_date ON metal_rates(business_id, rate_date);
```

---

## 5. Explicitly Deferred

The following are **not** part of the initial schema and should only be added when a concrete analytics or feature requirement demands them:

- Multi-store / location tables (a jewellery chain with many branches)
- Supplier/karigar tables
- Customer/CRM tables
- Payment/accounting tables
- Platinum or additional metal types (unless the dataset needs them)
- Role-based access control within a business (e.g., staff vs. owner)

---

## 6. Financial Terminology (must match ANALYTICS_FORMULAS.md)

Because jewelry accounting can carry nuance, this schema's fields map to documented definitions of Revenue, COGS, Gross Profit, Metal Cost, Making Charge, and Discount in ANALYTICS_FORMULAS.md. Any assumption baked into a column's meaning must be documented there, not left implicit.

---

## 7. Change Log

| Date | Change | Reason |
|---|---|---|
| (initial) | Created products, purchases, sales, metal_rates | Phase 0–1 minimal schema to unblock synthetic data + analytics work |
| 2026-07-25 | Upgraded to production PostgreSQL DDL with types, constraints, indexes | Phase 1 documentation upgrade |
| 2026-07-25 | Added `users` and `businesses` tables; added `business_id` FK to all core tables; updated metal_rates PK to composite `(business_id, rate_date)` | Multi-business SaaS architecture change |
