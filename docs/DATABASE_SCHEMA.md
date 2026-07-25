# DATABASE_SCHEMA.md

## Status

This document defines the schema for the **JewelMind-AI** multi-business SaaS platform. All tables that contain business data are scoped to a `business_id` foreign key. A query that aggregates across businesses without a `business_id` filter is a critical data-isolation bug (see PROJECT_RULES.md, rule 11).

## Database Technology

*   **Database**: MySQL (v8.0+)
*   **Access Layer**: SQLAlchemy ORM (v2.0+) using declarative mapping with `PyMySQL` driver
*   **Migrations**: Alembic
*   **Environment Configuration**: Credentials loaded via system environment variables (`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`) per [PROJECT_PLAN.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROJECT_PLAN.md).

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
│  (Global Reference Table)  │
├────────────────────────────┤
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
| user_id | INT AUTO_INCREMENT PRIMARY KEY | Auto-incremented primary key |
| email | VARCHAR(255) UNIQUE NOT NULL | Login identity |
| password_hash | VARCHAR(512) NOT NULL | bcrypt hash; never store plaintext |
| full_name | VARCHAR(255) NOT NULL | Display name |
| created_at | DATETIME | Auto-set on insert |
| updated_at | DATETIME | Auto-updated |

---

### Table 2: `businesses`
Every registered user may own one or more named jewellery businesses. This table is the multi-tenancy anchor — every business-data table references `business_id` from here.

| Column | Type | Notes |
|---|---|---|
| business_id | INT AUTO_INCREMENT PRIMARY KEY | Multi-tenancy anchor key |
| owner_user_id | INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE | Who owns this business |
| business_name | VARCHAR(255) NOT NULL | e.g., "Rajesh Jewellers" |
| owner_name | VARCHAR(255) | Contact name within the business |
| email | VARCHAR(255) | Business contact email |
| phone | VARCHAR(50) | Business contact phone |
| created_at | DATETIME | Auto-set on insert |
| updated_at | DATETIME | Auto-updated |

---

### Table 3: `products`
Master catalogue for each jewellery item belonging to a specific business.

| Column | Type | Notes |
|---|---|---|
| product_id | INT AUTO_INCREMENT PRIMARY KEY | |
| business_id | INT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE | **Data isolation key** |
| sku | VARCHAR(100) NOT NULL | Unique *per business* (not globally) |
| product_name | VARCHAR(255) NOT NULL | |
| category | VARCHAR(100) NOT NULL | Enum: chain, necklace, payal, coin, utensil, ring, bangle, earring |
| metal | VARCHAR(50) NOT NULL | Enum: gold, silver |
| purity | VARCHAR(50) NOT NULL | e.g., 22K, 24K, 18K, 925 |
| gross_weight | DECIMAL(10, 4) NOT NULL | Total piece weight in grams |
| net_weight | DECIMAL(10, 4) NOT NULL | Metal-only weight in grams |

> Unique constraint: `(business_id, sku)` — the same SKU may exist in different businesses.

---

### Table 4: `purchases`
Inventory inflows for a specific business.

| Column | Type | Notes |
|---|---|---|
| purchase_id | INT AUTO_INCREMENT PRIMARY KEY | |
| business_id | INT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE | **Data isolation key** |
| product_id | INT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE | |
| purchase_date | DATETIME NOT NULL | Transaction timestamp |
| quantity | INT NOT NULL | |
| weight | DECIMAL(10, 4) NOT NULL | |
| metal_rate | DECIMAL(12, 2) NOT NULL | Rate per gram at acquisition time |
| metal_cost | DECIMAL(12, 2) NOT NULL | |
| making_cost | DECIMAL(12, 2) NOT NULL | Labor paid to supplier/karigar |
| total_cost | DECIMAL(12, 2) NOT NULL | metal_cost + making_cost |

---

### Table 5: `sales`
Inventory outflows for a specific business. Price components are captured dynamically at billing time.

| Column | Type | Notes |
|---|---|---|
| sale_id | INT AUTO_INCREMENT PRIMARY KEY | |
| business_id | INT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE | **Data isolation key** |
| product_id | INT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE | |
| sale_date | DATETIME NOT NULL | Transaction timestamp |
| quantity | INT NOT NULL | |
| weight | DECIMAL(10, 4) NOT NULL | |
| selling_price | DECIMAL(12, 2) NOT NULL | Gross price before discount |
| making_charge | DECIMAL(12, 2) NOT NULL | Labor billed to customer |
| discount | DECIMAL(12, 2) NOT NULL DEFAULT 0.00 | Deducted from selling price |
| cost_basis | DECIMAL(12, 2) NOT NULL | Derived from purchases.total_cost for accurate GP |

---

### Table 6: `metal_rates`
Global commodity reference rates. Gold and Silver market rates are global reference data shared by all businesses on the platform. Records are populated automatically by the background Metal Rates Fetch Service (fetching and validating rates from a trusted external API) and stored in MySQL. Historical rates are retained indefinitely for **valuation history**, **trend analysis**, and **scenario simulation**.

| Column | Type | Notes |
|---|---|---|
| rate_date | DATE PRIMARY KEY | Global commodity rate date |
| gold_24k | DECIMAL(12, 2) NOT NULL | Rate per gram in INR |
| gold_22k | DECIMAL(12, 2) NOT NULL | Rate per gram in INR |
| silver | DECIMAL(12, 2) NOT NULL | Rate per gram in INR |

> Primary Key: `rate_date` (DATE) — Global reference table shared across all businesses (no `business_id`).

---

## 3. Key Relationships & Constraints

```
users (1) ──────────── (many) businesses
businesses (1) ──────── (many) products
businesses (1) ──────── (many) purchases
businesses (1) ──────── (many) sales
products (1) ──────────── (many) purchases
products (1) ──────────── (many) sales

-- Global Reference Data --
metal_rates (standalone table, Primary Key: rate_date)
```

**SKU Uniqueness**: `(business_id, sku)` — unique per business, not globally.

**Rate Lookup**: When joining `sales` or `purchases` to `metal_rates` for valuation, match on `DATE(sale_date) = rate_date`. Since `metal_rates` is a global market reference table, `business_id` is not present in `metal_rates`.

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
CREATE INDEX idx_metal_rates_date ON metal_rates(rate_date);
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
| 2026-07-25 | Upgraded database DDL with types, constraints, indexes | Phase 1 documentation upgrade |
| 2026-07-25 | Added `users` and `businesses` tables; added `business_id` FK to all core tables | Multi-business SaaS architecture change |
| 2026-07-26 | Replaced manual `metal_rates.csv` upload requirement with automated background Metal Rates Fetch Service | User experience & automated rate synchronization |
| 2026-07-26 | Standardized entire project database stack to MySQL (v8.0+) | Infrastructure standardization |
