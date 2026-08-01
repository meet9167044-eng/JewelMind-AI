# JewelMind-AI: Jewellery Business Intelligence Copilot

A **multi-business SaaS platform** built specifically for retail jewellers. Each user registers an account, creates one or more named jewellery businesses, uploads their store data (products, purchases, sales), and gets explainable analytics powered by deterministic Python/SQL and an AI Copilot that explains results — never calculates them.

---

## What It Does

A retail jeweller logs in, selects their business, uploads their store data, while the system automatically fetches current metal rates, and can ask questions in plain English:

- *"Why did my profit fall in June?"* — System decomposes the change into 5 additive drivers (volume, discount, making-charge, product-mix, metal-margin). AI explains each driver with View Evidence audit trace.
- *"Where is my money stuck?"* — System classifies 5 inventory ageing buckets, dead stock (>180d no sales), and stockout risks.
- *"What if silver falls 10%?"* — System calculates Weighted Acquisition Rate (WAR) and simulated valuation exposure float for this business's current inventory.

All results are strictly scoped to the authenticated user's selected business. No business can access another's data.

---

## Core Philosophy: Explainable AI (XAI)

$$\text{Data (per business)} \longrightarrow \text{Mathematics} \longrightarrow \text{Analysis} \longrightarrow \text{AI Explanation} \longrightarrow \text{View Evidence Trace}$$

Under no circumstances does the LLM perform financial calculations. All financial analysis is executed using deterministic Python (Pandas) and SQL, always filtered by `business_id`. The AI acts exclusively as an interpreter of verified results, providing a **[View Evidence]** trace button that maps every statement down to mathematical formulas and source database tables.

---

## Multi-Business SaaS Architecture

```
User (registers once via JWT auth)
  └── Business 1: "Rajesh Jewellers"
       ├── products   (business_id = 1)
       ├── purchases  (business_id = 1)
       └── sales      (business_id = 1)

Global Reference Data (Shared):
  └── metal_rates (PK: rate_date, auto-fetched by background scheduler)
```

- Every store transaction table (`products`, `purchases`, `sales`) includes a `business_id` foreign key.
- `metal_rates` is a global market reference table shared across all businesses (`rate_date DATE PRIMARY KEY`).
- Every analytics query for store transactions is filtered by `business_id`.
- `business_id` is resolved server-side from the JWT session — never trusted from the frontend or LLM.

---

## Technology Stack

*   **Frontend**: Next.js 15, TypeScript, Tailwind CSS, Recharts, Lucide Icons, Custom Luxury Dark-Mode Design System
*   **Backend**: FastAPI (Python 3.13), SQLAlchemy 2.0 ORM, Alembic migrations, APScheduler
*   **Auth**: JWT, bcrypt password hashing
*   **AI Engine**: Google Gemini SDK (`google-genai`), function calling with 4 analytics tools, 8-guardrail system prompt
*   **Database**: MySQL (v8.0+) with PyMySQL driver
*   **Data Analysis**: Pandas, NumPy
*   **Testing**: pytest (104 backend tests, 100% passing)

---

## Quickstart (Local Development)

### 1. Database Setup
Create MySQL database and set credentials in `.env`:
```sql
CREATE DATABASE jewelmind_db;
```

### 2. Backend Server
```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```
API Documentation available at: `http://localhost:8000/docs`

### 3. Frontend App
```bash
cd frontend
npm install
npm run dev
```
Open web application at: `http://localhost:3000`

### 4. Run Test Suite
```bash
python -m pytest backend/tests/ -v
```

---

## Documentation Index

All core system designs, requirements, rules, and formulations are in `/docs`:

| # | Document | Contents |
|---|---|---|
| 1 | [PROJECT_DEFINITION.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROJECT_DEFINITION.md) | Product scope, modules, MVP, multi-tenant user journey |
| 2 | [PROJECT_RULES.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROJECT_RULES.md) | Architectural guardrails incl. 6 multi-tenancy rules |
| 3 | [BUSINESS_DOMAIN.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/BUSINESS_DOMAIN.md) | Jewellery domain terminology + multi-business concepts |
| 4 | [DATABASE_SCHEMA.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/DATABASE_SCHEMA.md) | users, businesses, products, purchases, sales, metal_rates tables |
| 5 | [ANALYTICS_FORMULAS.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/ANALYTICS_FORMULAS.md) | All mathematical equations (business_id scoped) |
| 6 | [API_SPEC.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/API_SPEC.md) | Auth, business management, analytics, upload, Copilot endpoints |
| 7 | [AI_ARCHITECTURE.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/AI_ARCHITECTURE.md) | LLM tool schemas, business context injection, guardrails |
| 8 | [PROJECT_PLAN.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROJECT_PLAN.md) | 16-phase master execution plan with Cursor prompt templates |
| 9 | [PROGRESS.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROGRESS.md) | Completed milestones, current status, next tasks |

---

## Project Status

**All 16 Phases are COMPLETED** (16/16 phases complete, 114/114 tests passing):
- ✅ Phase 1: Domain & Architecture Locking
- ✅ Phase 2: Synthetic Data Generator
- ✅ Phase 3: Hand-Trace Verification
- ✅ Phase 4: FastAPI Infrastructure
- ✅ Phase 5: Authentication (Register/Login/JWT)
- ✅ Phase 6: Business Management (Multi-Tenant Layer)
- ✅ Phase 7: Core DB Models & Data Seeding
- ✅ Phase 8: Core Analytics Service
- ✅ Phase 9: Profit Diagnosis Engine
- ✅ Phase 10: Inventory Intelligence Engine
- ✅ Phase 11: Metal Exposure & Scenario Engine
- ✅ Phase 12: Data Upload Pipeline
- ✅ Phase 13: Next.js Frontend (All 11 pages & luxury dark-mode design system)
- ✅ Phase 14: AI Copilot & View Evidence (Gemini SDK + tool calling + audit trace)
- ✅ Phase 15: Action Center & Proactive Insights Engine
- ✅ Phase 16: E2E Testing, Polish & Demo Narrative Walkthrough
