# Master Project Execution Plan — JewelMind-AI

This document is the master, step-by-step development roadmap for **JewelMind-AI: Explainable Analytics and Scenario Intelligence for Retail Jewellers**.

It organizes development into **16 controlled, bite-sized phases**. Each phase specifies:
- Key objectives
- Relevant files and directories
- Detailed implementation instructions
- Exact Cursor/Codex prompts
- Mandatory verification tests & gates
- Recommended Git commit messages

> [!IMPORTANT]
> **Architecture Change (2026-07-25)**: This project is a **multi-business SaaS platform**. Every user can register and create one or more named jewellery businesses. All data, analytics, and AI Copilot queries are strictly scoped to a single `business_id`. Cross-business data access is a critical bug. Two new phases (Phase 4: Authentication and Phase 5: Business Management) have been added before the FastAPI/data phases. All subsequent phase numbers have shifted accordingly. See [PROJECT_DEFINITION.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROJECT_DEFINITION.md) and [DATABASE_SCHEMA.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/DATABASE_SCHEMA.md) for the full architectural rationale.

---

## Architecture & Development Guardrails

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          JEWELLERY BI COPILOT (SaaS)                     │
│                                                                          │
│  AUTH ──► BUSINESS SELECT ──► DATA ──► MATH ──► ANALYSIS ──► AI         │
│  (JWT)    (business_id)       (SQL)    (Pandas)  (Engine)     (Copilot)  │
└──────────────────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Core Architectural Rules**:
> 1. Financial calculations must **never** be performed by the LLM. Python and SQL calculate 100% of all financial metrics deterministically.
> 2. Every analytics query must be filtered by `business_id`. A query that crosses business boundaries is a data-isolation bug.
> 3. `business_id` must always be resolved server-side from the JWT session. Never trust it from the frontend directly.

---

## Phase Roadmap Overview

| Phase | Title | Focus Area | Status |
|---|---|---|---|
| **Phase 1** | Domain & Architecture Locking | Documentation & Specs | **Completed** |
| **Phase 2** | Synthetic Data Generator | Data Generation & Ground Truth | **Completed** |
| **Phase 3** | Hand-Trace & Verification | Math Verification | *Next* |
| **Phase 4** | FastAPI Infrastructure | Backend Foundation | *Pending* |
| **Phase 5** | Authentication (Register/Login) | User Auth & JWT | *Pending* |
| **Phase 6** | Business Management | Multi-Tenant Business Layer | *Pending* |
| **Phase 7** | Core DB Models & Data Seeding | Database Persistence (business_id) | *Pending* |
| **Phase 8** | Core Analytics Service | Basic Analytics (scoped) | *Pending* |
| **Phase 9** | Profit Diagnosis Engine | Variance Decomposition | *Pending* |
| **Phase 10** | Inventory Intelligence Engine | Ageing & Coverage | *Pending* |
| **Phase 11** | Metal Exposure & Scenario Engine | Risk & Simulation | *Pending* |
| **Phase 12** | Data Upload Pipeline | Ingestion & Business Tagging | *Pending* |
| **Phase 13** | Next.js Frontend | Web UI, Auth, Business Hub, Charts | *Pending* |
| **Phase 14** | AI Copilot & Tool Calling | LLM & View Evidence (scoped) | *Pending* |
| **Phase 15** | Action Center & Insights | Proactive Alert Engine | *Pending* |
| **Phase 16** | E2E Testing & Demo Narrative | Testing & Presentation | *Pending* |

---

## Phase 1: Domain & Architecture Locking

### Objective
Establish all project specifications, database schema, math formulas, API endpoints, LLM guardrails, and business domain knowledge prior to writing application code.

### Files Created/Modified
- [PROJECT_DEFINITION.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROJECT_DEFINITION.md)
- [PROJECT_RULES.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROJECT_RULES.md)
- [BUSINESS_DOMAIN.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/BUSINESS_DOMAIN.md)
- [DATABASE_SCHEMA.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/DATABASE_SCHEMA.md)
- [ANALYTICS_FORMULAS.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/ANALYTICS_FORMULAS.md)
- [API_SPEC.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/API_SPEC.md)
- [AI_ARCHITECTURE.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/AI_ARCHITECTURE.md)
- [PROGRESS.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROGRESS.md)
- [README.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/README.md)

### Status
**100% Completed**

> [!NOTE]
> All Phase 1 documentation was updated on 2026-07-25 to reflect the multi-business SaaS architecture. The database schema now includes `users` and `businesses` tables, and all core tables include `business_id` foreign keys.

---

## Phase 2: Synthetic Data Generator & Story Injection

### Objective
Create a standalone Python script that generates realistic jewellery store datasets with known ground-truth business scenarios embedded. These datasets are **development/testing fixtures only** — the production system supports arbitrary uploaded datasets from any business.

### Generated Files
- `data/products.csv` — 500 products
- `data/purchases.csv` — 1,255 acquisition records
- `data/sales.csv` — 10,190 transactions spanning 12 months
- `data/metal_rates.csv` — 365 daily rates

### Ground-Truth Stories Injected
1. **June Profit Drop** — Gold chain volume -14%, discount rate +1.6pp, making charges -12.7%.
2. **July Silver Fall** — Silver rate drops ~8.5% on July 1st.
3. **Dead Stock** — 17 items with purchase dates >180 days and zero sales.

### Status
**100% Completed** — `backend/scripts/generate_data.py` and `backend/scripts/verify_phase2.py`

> [!NOTE]
> The synthetic data does not include `business_id` columns yet (it pre-dates the SaaS architecture decision). When Phase 7 seeds the database, the seeder will assign all synthetic data to a demo business (e.g., `business_id=1`) created during database initialization.

---

## Phase 3: Hand-Trace & Calculation Verification

### Objective
Perform a manual mathematical trace of a sample product through purchase and sale to verify formula logic before building code APIs.

### Steps
1. Pick product `GC202` (product_id=102) from `data/products.csv`.
2. Trace its purchase record in `data/purchases.csv` (metal cost + making cost = total cost).
3. Trace all sales of product 102 in `data/sales.csv`.
4. Calculate manually:
   - Gross Revenue = $\sum \text{selling\_price}$
   - Net Revenue = $\sum (\text{selling\_price} - \text{discount})$
   - COGS = $\sum \text{cost\_basis}$
   - Gross Profit = $\text{Net Revenue} - \text{COGS}$
   - Making Charge Realization = $\frac{\sum \text{making\_charge}}{\text{Total Weight}}$
5. Compare manual calculations against formulas in [ANALYTICS_FORMULAS.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/ANALYTICS_FORMULAS.md).

### Verification Gate
- Create `backend/scripts/verify_hand_trace.py`.
- Assert that manual calculations match formula outputs exactly.
- Confirm formulas operate on a single business's data slice.

### Git Commit
`docs: verify hand-traced financial calculations against analytic formulas`

---

## Phase 4: FastAPI Infrastructure Setup

### Objective
Initialize the FastAPI application structure, configure PostgreSQL connection via SQLAlchemy, and set up Alembic migrations. No models, routes, or business logic yet — just the skeleton.

### Files to Create
- `backend/requirements.txt` (fastapi, uvicorn, sqlalchemy, psycopg2-binary, alembic, pydantic, python-jose, passlib, bcrypt, pandas, pytest)
- `backend/app/main.py`
- `backend/app/database.py`
- `backend/app/config.py`
- `alembic.ini` & `backend/alembic/`

### Cursor Prompt Template
```text
Read docs/API_SPEC.md and docs/PROJECT_RULES.md.

Initialize the FastAPI backend infrastructure inside backend/.

Requirements:
1. Create requirements.txt with FastAPI, SQLAlchemy, Alembic, psycopg2-binary, pandas, pydantic, python-jose, passlib[bcrypt], and pytest.
2. Setup database.py connecting to PostgreSQL using SQLAlchemy 2.0 async/sync style.
3. Create main.py with CORS middleware and GET /health endpoint.
4. Setup Alembic configuration.
5. Do NOT create database models, routes, or business logic yet.
```

### Verification Gate
- Run `uvicorn backend.app.main:app --reload`.
- Access `http://localhost:8000/health` → verify `{"status": "ok"}`.
- Access `http://localhost:8000/docs` → verify Swagger UI loads.

### Git Commit
`feat: setup FastAPI backend infrastructure and PostgreSQL database connection`

---

## Phase 5: Authentication (Register / Login)

### Objective
Build the user authentication layer: registration, login, JWT issuance, and a reusable auth dependency that extracts `user_id` from every authenticated request.

### Files to Create
- `backend/app/models/user.py` (SQLAlchemy User model)
- `backend/app/schemas/auth.py` (Pydantic: RegisterRequest, LoginRequest, TokenResponse)
- `backend/app/services/auth_service.py` (register, login, hash_password, verify_password, create_jwt)
- `backend/app/routers/auth.py` (POST /api/auth/register, POST /api/auth/login)
- `backend/app/dependencies/auth.py` (get_current_user dependency)
- `backend/tests/test_auth.py`

### Cursor Prompt Template
```text
Read docs/DATABASE_SCHEMA.md (Table 1: users) and docs/API_SPEC.md (Section 3).

Implement the user authentication layer.

Requirements:
1. Create SQLAlchemy User model with columns: user_id, email (unique), password_hash, full_name, created_at, updated_at.
2. Implement auth_service.py with: register(email, password, full_name), login(email, password), create_access_token(user_id).
3. Use bcrypt for password hashing. Use python-jose for JWT (HS256, 30-day expiry).
4. Expose POST /api/auth/register (201) and POST /api/auth/login (200 with token).
5. Create a FastAPI dependency get_current_user(token) that decodes the JWT and returns the authenticated user object. This dependency will be used by ALL subsequent protected routes.
6. Write pytest tests in backend/tests/test_auth.py covering: successful registration, duplicate email rejection, successful login, and invalid credentials rejection.
7. Do NOT create any business logic, products, purchases, or analytics yet.
```

### Verification Gate
- Run `pytest backend/tests/test_auth.py` — all tests pass.
- Test via Swagger: `POST /api/auth/register` → user created; `POST /api/auth/login` → JWT returned.
- Verify the JWT cannot be decoded to access another user's data (confirm JWT contains only `user_id`).

### Git Commit
`feat: add user registration, login, JWT authentication, and auth dependency`

---

## Phase 6: Business Management (Multi-Tenant Layer)

### Objective
Build the business management layer: create, list, and retrieve named jewellery businesses. This is the multi-tenancy anchor — `business_id` from this layer will be validated on every subsequent request.

### Files to Create
- `backend/app/models/business.py` (SQLAlchemy Business model)
- `backend/app/schemas/business.py` (Pydantic: CreateBusinessRequest, BusinessResponse)
- `backend/app/services/business_service.py` (create_business, list_businesses, get_business_if_owner)
- `backend/app/routers/businesses.py` (GET /api/businesses, POST /api/businesses, GET /api/businesses/{business_id})
- `backend/app/dependencies/business.py` (get_owned_business dependency)
- `backend/tests/test_businesses.py`

### Key Design: `get_owned_business` Dependency
This is the most critical dependency in the application. It:
1. Takes `business_id` from the path parameter.
2. Takes `current_user` from the JWT dependency.
3. Queries: `SELECT * FROM businesses WHERE business_id = ? AND owner_user_id = ?`
4. Returns the business object if found — raises `403 Forbidden` if not.

**This dependency must be applied to every route that touches business data.**

### Cursor Prompt Template
```text
Read docs/DATABASE_SCHEMA.md (Tables 1 & 2) and docs/API_SPEC.md (Section 4).

Implement the business management layer.

Requirements:
1. Create SQLAlchemy Business model with columns per DATABASE_SCHEMA.md (business_id, owner_user_id FK, business_name, owner_name, email, phone, created_at, updated_at).
2. Implement business_service.py with: create_business(user_id, data), list_businesses(user_id), get_business_if_owner(business_id, user_id).
3. Expose GET /api/businesses and POST /api/businesses. Both require authentication via get_current_user dependency.
4. Expose GET /api/businesses/{business_id} — requires get_current_user AND ownership check. Return 403 if user does not own the business.
5. Create a reusable FastAPI dependency `get_owned_business(business_id, current_user)` that encapsulates the ownership check. This will be reused by ALL analytics, upload, and Copilot routes.
6. Write pytest tests covering: create business, list businesses (only own businesses returned), ownership enforcement (user A cannot access user B's business).
```

### Verification Gate
- Run `pytest backend/tests/test_businesses.py` — all tests pass.
- Create two users (A and B), create a business for A. Confirm user B's JWT returns 403 when accessing user A's business_id.
- This is the core security gate — the test must explicitly verify cross-business access is rejected.

### Git Commit
`feat: add business management endpoints, ownership validation, and get_owned_business dependency`

---

## Phase 7: Core Database Models & Data Seeding

### Objective
Define SQLAlchemy ORM models for all business-data tables — all including `business_id` — run Alembic migrations, and seed the Phase 2 synthetic datasets into a demo business.

### Files to Create
- `backend/app/models/product.py` (with business_id FK)
- `backend/app/models/purchase.py` (with business_id FK)
- `backend/app/models/sale.py` (with business_id FK)
- `backend/app/models/metal_rate.py` (with business_id FK; composite PK)
- `backend/scripts/seed_db.py` (creates demo user + demo business, tags all CSV rows to business_id=1)

### Critical Seeding Instructions
The seeder must:
1. Create a demo user (`demo@jewelmind.com`, password: `demo123`).
2. Create a demo business (`Rajesh Jewellers Demo`) owned by the demo user.
3. Read all 4 CSVs from `data/` and insert every row with `business_id = 1`.
4. The SKU uniqueness constraint applies per `(business_id, sku)`, not globally.
5. For `metal_rates`, the composite primary key is `(business_id, rate_date)`.

### Cursor Prompt Template
```text
Read docs/DATABASE_SCHEMA.md (Tables 3-6) and docs/API_SPEC.md.

Implement SQLAlchemy ORM models and database seeding.

Requirements:
1. Create Product, Purchase, Sale, and MetalRate models. Every model must include business_id as a NOT NULL foreign key to businesses.business_id with ON DELETE CASCADE.
2. Add the composite primary key on metal_rates: (business_id, rate_date).
3. Add the unique constraint on products: (business_id, sku).
4. Generate and run Alembic migration to create all tables.
5. Build backend/scripts/seed_db.py that:
   a. Creates demo user and demo business if they do not exist.
   b. Reads all 4 CSVs from data/ and inserts rows tagged with business_id=1.
6. Do NOT add any analytics routes yet.
```

### Verification Gate
- Run `python backend/scripts/seed_db.py`.
- Query database: all rows in products, purchases, sales, metal_rates have `business_id = 1`.
- Verify demo user can log in and retrieve their business via the API.

### Git Commit
`feat: add business-scoped SQLAlchemy models, Alembic migrations, and demo data seeder`

---

## Phase 8: Core Analytics Service

### Objective
Build deterministic Python services for basic financial metrics (Revenue, COGS, Gross Profit, Monthly Comparison) per [ANALYTICS_FORMULAS.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/ANALYTICS_FORMULAS.md). All functions accept `business_id` and filter SQL queries accordingly.

### Files to Create
- `backend/app/services/analytics_service.py`
- `backend/app/routers/analytics.py`
- `backend/tests/test_analytics.py`

### Key Functions (all accept `business_id` as first argument)
- `calculate_revenue(db, business_id, start_date, end_date)`
- `calculate_cogs(db, business_id, start_date, end_date)`
- `calculate_gross_profit(db, business_id, start_date, end_date)`
- `compare_months(db, business_id, month_b, month_a)`

### Cursor Prompt Template
```text
Read docs/ANALYTICS_FORMULAS.md (Section 1), docs/API_SPEC.md (Section 6), and docs/PROJECT_RULES.md (Rules 11-12).

Implement core analytics service functions in backend/app/services/analytics_service.py.

Requirements:
1. Implement calculate_revenue, calculate_cogs, calculate_gross_profit, and compare_months.
2. Every function must accept business_id as the first parameter. Every SQL/ORM query must filter WHERE business_id = business_id. This is a non-negotiable multi-tenancy rule.
3. Expose endpoints under /api/businesses/{business_id}/analytics/ per API_SPEC.md. Use the get_owned_business dependency from Phase 6 for all routes.
4. Use SQLAlchemy / Pandas for deterministic calculation. Do not use LLMs.
5. Write unit tests in backend/tests/test_analytics.py — create separate test businesses to confirm results are isolated per business_id.
```

### Verification Gate
- Run `pytest backend/tests/test_analytics.py` — all tests pass.
- Multi-tenancy isolation test: Insert sales for business_id=1 and business_id=2. Verify `calculate_revenue(db, 1, ...)` does NOT include business_id=2 revenue.

### Git Commit
`feat: implement business-scoped revenue, COGS, and monthly comparison analytics`

---

## Phase 9: Flagship Profit Diagnosis Engine

### Objective
Build the variance decomposition engine that breaks down profit changes between two periods into 5 additive drivers: Volume, Discount, Making Charge, Product Mix, and Metal Margin — all filtered by `business_id`.

### Files to Create
- `backend/app/services/profit_diagnosis_service.py`
- `backend/tests/test_profit_diagnosis.py`

### Equations Implemented (see ANALYTICS_FORMULAS.md Section 2)
- $\Delta GP_{\text{vol}} = (W_B - W_A) \times \text{Margin Rate}_A$
- $\Delta GP_{\text{disc}} = - (d_B - d_A) \times W_B$
- $\Delta GP_{\text{labor}} = (M_B - M_A) \times W_B$
- $\Delta GP_{\text{mix}} = \sum_c \left( \frac{W_{B,c}}{W_B} - \frac{W_{A,c}}{W_A} \right) \times W_B \times \text{Margin Rate}_{A,c}$
- $\Delta GP_{\text{metal}} = \text{Residual Variance}$

### Cursor Prompt Template
```text
Read docs/ANALYTICS_FORMULAS.md (Section 2), docs/API_SPEC.md, and docs/PROJECT_RULES.md (Rules 11-12).

Implement the Profit Diagnosis Variance Decomposition engine.

Requirements:
1. Implement analyze_profit_change(db, business_id, target_month, baseline_month).
2. All queries must filter by business_id.
3. Calculate exact driver contributions: volume, discount, making charge, mix, metal margin.
4. Expose POST /api/businesses/{business_id}/analytics/profit-diagnosis using get_owned_business dependency.
5. Write pytest tests asserting the synthetic June scenario returns: volume impact ~-₹52K, discount ~-₹31K, making charge ~-₹21K, mix ~-₹14K. Total ~-₹1.18L.
```

### Verification Gate
- Run `pytest backend/tests/test_profit_diagnosis.py`.
- **Assert Ground Truth**: June vs May returns correct driver decomposition for business_id=1.
- Verify the same endpoint for a different `business_id` (with no data) returns zero deltas — not the same data.

### Git Commit
`feat: implement business-scoped profit diagnosis variance decomposition engine`

---

## Phase 10: Inventory Intelligence Engine

### Objective
Build inventory ageing calculations, stock coverage analysis, and classification logic (fast movers, slow movers, dead stock, stockout risks) — all filtered by `business_id`.

### Files to Create
- `backend/app/services/inventory_service.py`
- `backend/tests/test_inventory.py`

### Logic Implemented
- Ageing Buckets: 0–30, 31–90, 91–180, 181–365, 365+ days.
- Stock Coverage: $\text{Coverage}_c = \frac{\text{Inventory Weight}}{\text{Avg Daily Sales Weight (30d)}}$
- Dead Stock: Age > 180 days & 0 sales in 90 days.
- Stockout Risk: Fast mover & Coverage < 15 days.

### Cursor Prompt Template
```text
Read docs/ANALYTICS_FORMULAS.md (Section 3), docs/API_SPEC.md, and docs/PROJECT_RULES.md (Rules 11-12).

Implement inventory intelligence in backend/app/services/inventory_service.py.

Requirements:
1. Implement calculate_inventory_age(db, business_id) — grouping unsold stock into ageing buckets.
2. Implement classify_inventory_performance(db, business_id) — dead stock, slow movers, stockout risks.
3. All queries must filter by business_id.
4. Expose GET /api/businesses/{business_id}/analytics/inventory-age and GET .../inventory-performance with get_owned_business dependency.
5. Write tests asserting the 17 synthetic dead-stock items appear for business_id=1 and NOT for any other business.
```

### Verification Gate
- Run `pytest backend/tests/test_inventory.py`.
- Verify 17 synthetic aged items appear in dead stock for business_id=1.
- Verify the same endpoint for business_id=2 (no data) returns an empty dead stock list.

### Git Commit
`feat: implement business-scoped inventory ageing, stock coverage, and dead stock classification`

---

## Phase 11: Metal Exposure & Scenario Engine

### Objective
Build precious metal valuation metrics (Weighted Acquisition Rate, Valuation Exposure) and the rate-shift scenario simulator — all filtered by `business_id`.

### Files to Create
- `backend/app/services/metal_service.py`
- `backend/tests/test_metal.py`

### Files to Create
- `backend/app/services/metal_service.py`
- `backend/app/services/metal_rate_fetcher.py` (External Commodity API Integration)
- `backend/app/services/scheduler.py` (APScheduler Background Job for Periodic Fetching)
- `backend/tests/test_metal.py`

### Formulas & Integration Implemented
- **External Rate Sync**: Background scheduler periodically calls external commodity API, normalizes rates, and persists daily 24K, 22K, and silver rates into PostgreSQL (`metal_rates` table).
- **Weighted Acquisition Rate**: $\text{WAR} = \frac{\sum \text{metal\_cost}}{\sum \text{net\_weight}}$
- **Valuation Exposure**: $\text{Net Weight} \times (R_{\text{today}} \times \text{Purity} - \text{WAR})$
- **Scenario Simulation**: Rate shift by $x\% \rightarrow$ recalculate valuation movement.

### Cursor Prompt Template
```text
Read docs/ANALYTICS_FORMULAS.md (Sections 4 & 5), docs/API_SPEC.md (Sections 6, 7 & 10), and docs/PROJECT_RULES.md (Rules 11, 20, 21).

Implement metal exposure, scenario simulation, and automatic metal rate fetching.

Requirements:
1. Implement metal_rate_fetcher.py to fetch current Gold and Silver board rates from external commodity API and store in PostgreSQL (metal_rates table).
2. Implement background scheduler service (scheduler.py using APScheduler) for periodic automated rate updates.
3. Expose POST /api/system/metal-rates/refresh per API_SPEC.md.
4. Implement calculate_metal_exposure(db, business_id, metal) and simulate_metal_rate_shift(db, business_id, metal, change_percent) querying stored DB rates only.
5. All queries must filter by business_id.
6. Write tests verifying July silver fall shows expected valuation exposure and confirming background fetcher updates metal_rates table cleanly.
```

### Verification Gate
- Run `pytest backend/tests/test_metal.py`.
- Verify metal rate fetcher pulls rates and stores them in PostgreSQL `metal_rates` table.
- Verify silver valuation exposure calculation matches synthetic scenario using stored rates.
- Verify analytics functions never invoke external API directly.

### Git Commit
`feat: implement metal rate fetch service, background scheduler, metal exposure engine, and scenario simulation`

---

## Phase 12: Data Upload & Validation Pipeline

### Objective
Build the CSV/Excel upload pipeline for **Products**, **Purchases**, and **Sales** with validation, type checking, and a Data Quality Report. (Metal rates are handled automatically by the Phase 11 Metal Rate Fetch Service). Every uploaded row is tagged with the `business_id` of the selected business — determined server-side, never from the file itself.

### Files to Create
- `backend/app/services/upload_service.py`
- `backend/app/routers/upload.py`

### Validation Rules
- Required columns present per [DATABASE_SCHEMA.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/DATABASE_SCHEMA.md).
- Non-negative weight, price, and rate assertions.
- Valid date formatting (`YYYY-MM-DD` or ISO timestamp).
- Graceful error handling: `400 Bad Request` with row/column failure details.

### Business Tagging Rule
The upload service must:
1. Accept `business_id` from the validated route parameter (verified via `get_owned_business`).
2. Inject `business_id` into every row before `INSERT` — the CSV file itself must never supply this column.

### Cursor Prompt Template
```text
Read docs/API_SPEC.md (Section 5), docs/DATABASE_SCHEMA.md, and docs/PROJECT_RULES.md (Rules 9, 11, 14, 20).

Implement the data upload pipeline for Products, Purchases, and Sales.

Requirements:
1. Expose POST /api/businesses/{business_id}/upload/{dataset_type} for dataset_type in [products, purchases, sales]. (Shopkeeper does not upload metal_rates manually).
2. Validate required columns, data types, and non-negative constraints.
3. CRITICAL: Inject business_id into every row server-side before inserting. The CSV does NOT supply business_id.
4. Return upload_id, rows_processed, and any validation warnings.
5. Expose GET /api/businesses/{business_id}/upload/data-quality-report/{upload_id}.
```

### Verification Gate
- Upload a valid products CSV for business_id=1 → rows appear in DB with business_id=1.
- Upload an invalid CSV (missing `purchase_date`) → `400` with exact error message.
- Verify that rows uploaded for business_id=1 do not appear in analytics queries for business_id=2.

### Git Commit
`feat: implement business-tagged CSV upload pipeline with validation and quality report`

---

## Phase 13: Next.js Frontend

### Objective
Build the full Next.js frontend: login/register pages, business hub, and all analytics pages. Authentication state and the selected `business_id` are managed in the frontend and passed with every API call.

### App Structure (`frontend/`)
- `src/app/(auth)/login/page.tsx` — Login page
- `src/app/(auth)/register/page.tsx` — Registration page
- `src/app/businesses/page.tsx` — Business Hub (list & create)
- `src/app/businesses/[business_id]/dashboard/page.tsx` — Dashboard
- `src/app/businesses/[business_id]/profit/page.tsx` — Profit Intelligence
- `src/app/businesses/[business_id]/inventory/page.tsx` — Inventory Intelligence
- `src/app/businesses/[business_id]/metal/page.tsx` — Metal Exposure
- `src/app/businesses/[business_id]/simulator/page.tsx` — Scenario Simulator
- `src/app/businesses/[business_id]/insights/page.tsx` — Action Center
- `src/app/businesses/[business_id]/upload/page.tsx` — Data Upload
- `src/app/businesses/[business_id]/copilot/page.tsx` — AI Copilot

### Key Routing Principle
The `business_id` from the URL (`/businesses/[business_id]/dashboard`) must match the business the user owns. The frontend sends the JWT in every request header. The backend validates ownership independently — the frontend never bypasses this.

### Cursor Prompt Template
```text
Read docs/PROJECT_DEFINITION.md (Product Structure), docs/API_SPEC.md, and docs/AI_ARCHITECTURE.md.

Build the Next.js frontend inside frontend/.

Requirements:
1. Setup Next.js with TypeScript, Tailwind CSS, shadcn/ui components, and Recharts.
2. Build auth pages: login and register forms.
3. Build Business Hub: list of owned businesses + create new business form.
4. Build per-business layout with sidebar navigation (Dashboard, Profit, Inventory, Metal, Simulator, Insights, Upload, Copilot).
5. All analytics page API calls must include the JWT auth header and use the business_id from the URL params.
6. Implement Dashboard, Profit Diagnosis, Inventory Ageing, Metal Exposure, Scenario Simulator pages.
```

### Verification Gate
- Register new user → login → create business → upload CSV → see dashboard metrics.
- Log in as a different user → confirm they cannot see the first user's business.

### Git Commit
`feat: build full Next.js frontend with auth, business hub, and per-business analytics pages`

---

## Phase 14: AI Copilot & Tool Calling

### Objective
Integrate the LLM with function/tool calling. The Copilot operates strictly within the `business_id` context — the `business_id` is injected server-side and never visible to or supplied by the LLM.

### Files to Create
- `backend/app/services/copilot_service.py`
- `backend/app/routers/copilot.py`
- `frontend/src/components/copilot/CopilotDrawer.tsx`
- `frontend/src/components/copilot/ViewEvidenceModal.tsx`

### Business Context Injection
The `copilot_service.py` must:
1. Accept `business_id` from the validated route (via `get_owned_business`).
2. Inject `business_id` as a closure parameter into every tool call handler — not as an LLM-visible parameter.
3. Generate a dynamic system prompt from the template in `AI_ARCHITECTURE.md` that includes the `business_name` string.

### Cursor Prompt Template
```text
Read docs/AI_ARCHITECTURE.md and docs/API_SPEC.md (Sections 8 & 9).

Implement the AI Copilot tool-calling layer.

Requirements:
1. Expose POST /api/businesses/{business_id}/copilot/ask using get_owned_business dependency.
2. Inject business_id into every tool handler as a closure — do NOT make it an LLM-visible tool parameter.
3. Implement tool handlers calling the analytics services from Phases 8-11, each passing business_id.
4. Enforce system prompt guardrails from AI_ARCHITECTURE.md (7 rules), including the prohibition on referencing other businesses.
5. Return response_text + evidence object per API_SPEC.md.
6. Build Copilot Drawer UI with [View Evidence] button and drill-down modal.
```

### Verification Gate
- Ask: *"Why did my profit fall in June?"* → AI calls `analyze_profit_change`, receives scoped payload, explains correctly.
- Click [View Evidence] → modal shows formula and driver breakdown.
- Verify the Copilot cannot return data for a business the user does not own (ownership dependency blocks it before LLM is called).

### Git Commit
`feat: implement business-scoped AI Copilot, tool calling, guardrails, and View Evidence trace UI`

---

## Phase 15: Action Center & Proactive Insights Engine

### Objective
Create a rule-based Insight Engine that scans analytics outputs after every data refresh and produces a prioritized Action Center — scoped to `business_id`.

### Files to Create
- `backend/app/services/insight_service.py`
- `backend/app/routers/insights.py`
- `frontend/src/app/businesses/[business_id]/insights/page.tsx`

### Insight Rules Implemented
1. **Aged Inventory Alert (High Priority)**: Inventory age > 180 days and value > ₹1L.
2. **Stockout Warning (Medium Priority)**: Fast-moving item stock coverage < 15 days.
3. **Discount Escalation (Low Priority)**: Average discount rate increases > 25% month-over-month.

### Cursor Prompt Template
```text
Read docs/AI_ARCHITECTURE.md (Insight Engine) and docs/API_SPEC.md (Section 8).

Implement the proactive Insight Engine and Action Center.

Requirements:
1. Implement insight_service.py running rule checks over analytics data for a given business_id.
2. Expose GET /api/businesses/{business_id}/insights with get_owned_business dependency.
3. Build Action Center page showing categorized alert cards (High/Medium/Low) with evidence links.
```

### Verification Gate
- Refresh analytics → Action Center shows:
  - 🔴 High: ₹4.2L inventory older than 180 days.
  - 🟠 Medium: 11 fast-moving products facing stockout risk.
  - 🟡 Low: Average discount increased from 3.2% to 4.8%.
- Verify insights are scoped to business_id=1 and do not appear for business_id=2.

### Git Commit
`feat: implement business-scoped rule-based insight engine and proactive Action Center UI`

---

## Phase 16: End-to-End Testing, Polish & Demo Narrative

### Objective
Perform end-to-end verification, finalize UI polish, run automated test suites, and rehearse the final story-driven presentation.

### Tasks
1. Run full Pytest suite:
   ```bash
   pytest backend/tests/
   ```
2. Verify test coverage: auth, business management, analytics, profit diagnosis, inventory, metal exposure, upload, and multi-tenancy isolation.
3. Polish UI: typography, HSL color palette, dark mode, hover transitions.
4. Execute story-driven demo flow:
   - **Step 0**: Register as Rajesh → Login → Create "Rajesh Jewellers" business.
   - **Step 1**: Upload 3 CSV files (Products, Purchases, Sales) → System automatically synchronizes metal rates via background Metal Rates Fetch Service → Review Data Quality Report.
   - **Step 2**: Open Dashboard → See KPIs & June profit drop (-13.4%).
   - **Step 3**: Ask Copilot: *"Why did profit fall in June?"* → AI explains drivers → View Evidence modal.
   - **Step 4**: Ask Copilot: *"Where is my money stuck?"* → View Dead Stock list.
   - **Step 5**: Open Scenario Simulator → drag Silver slider to -10% → see simulated exposure.
   - **Closing**: *"Traditional ERPs tell Rajesh what happened. JewelMind-AI helps him understand why it happened, where the risks are, and what deserves attention next — for his business, and his business alone."*

### Verification Gate
- All pytest tests pass.
- Multi-tenancy: two separate user sessions confirmed to see only their own business data.
- Full demo story executes without UI glitches or backend errors.

### Git Commit
`docs: finalize E2E testing, UI polish, multi-tenancy verification, and demo walkthrough`

---

## Summary Checklist & Progress Tracking

- [x] **Phase 1**: Domain & Architecture Locking
- [x] **Phase 2**: Synthetic Data Generator
- [ ] **Phase 3**: Hand-Trace Verification
- [ ] **Phase 4**: FastAPI Infrastructure
- [ ] **Phase 5**: Authentication (Register/Login/JWT)
- [ ] **Phase 6**: Business Management (Multi-Tenant Layer)
- [ ] **Phase 7**: Core DB Models & Data Seeding (with business_id)
- [ ] **Phase 8**: Core Analytics Service (business_id scoped)
- [ ] **Phase 9**: Profit Diagnosis Engine (business_id scoped)
- [ ] **Phase 10**: Inventory Intelligence Engine (business_id scoped)
- [ ] **Phase 11**: Metal Exposure & Scenario Engine (business_id scoped)
- [ ] **Phase 12**: Data Upload Pipeline (business tagging)
- [ ] **Phase 13**: Next.js Frontend (auth + business hub + analytics)
- [ ] **Phase 14**: AI Copilot & View Evidence (business_id scoped)
- [ ] **Phase 15**: Action Center & Insights (business_id scoped)
- [ ] **Phase 16**: E2E Testing & Demo Narrative
