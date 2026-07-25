# JewelMind-AI: Jewellery Business Intelligence Copilot

A **multi-business SaaS platform** built specifically for retail jewellers. Each user registers an account, creates one or more named jewellery businesses, uploads their own data, and gets explainable analytics powered by deterministic Python/SQL and an AI Copilot that explains results — never calculates them.

---

## What It Does

A retail jeweller logs in, selects their business, uploads their data (products, purchases, sales, metal rates), and can ask questions in plain English:

- *"Why did my profit fall in June?"* — System decomposes the change into volume, discount, making-charge, and product-mix effects. AI explains each driver with evidence.
- *"Where is my money stuck?"* — System classifies aged inventory, dead stock, and stockout risks.
- *"What if silver falls 10%?"* — System calculates simulated valuation exposure for this business's current inventory.

All results are scoped to the authenticated user's selected business. No business can access another's data.

---

## Core Philosophy: Explainable AI

$$\text{Data (per business)} \longrightarrow \text{Mathematics} \longrightarrow \text{Analysis} \longrightarrow \text{AI Explanation} \longrightarrow \text{Decision Support}$$

Under no circumstances does the LLM perform financial calculations. All financial analysis is executed using deterministic Python (Pandas) and SQL, always filtered by `business_id`. The AI acts exclusively as an interpreter of verified results.

---

## Multi-Business SaaS Architecture

```
User (registers once)
  └── Business 1: "Rajesh Jewellers"
       ├── products   (business_id = 1)
       ├── purchases  (business_id = 1)
       ├── sales      (business_id = 1)
       └── metal_rates (business_id = 1)
  └── Business 2: "Mehta Silver Mart" (future)
       └── ... (completely independent data)
```

- Every core table includes a `business_id` foreign key.
- Every analytics query is filtered by `business_id`.
- `business_id` is resolved server-side from the JWT session — never trusted from the frontend.

---

## Technology Stack

*   **Frontend**: Next.js, TypeScript, Tailwind CSS, shadcn/ui, Recharts
*   **Backend**: FastAPI (Python), SQLAlchemy ORM, Alembic migrations
*   **Auth**: JWT (python-jose), bcrypt password hashing
*   **Database**: PostgreSQL
*   **Data Analysis**: Pandas, NumPy
*   **Testing**: pytest

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

## Development Workflow

Before writing code, always run through this loop:

1. Read **[PROJECT_RULES.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROJECT_RULES.md)** and **[PROGRESS.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROGRESS.md)**.
2. Implement the feature, filtering all queries by `business_id`.
3. Write tests — include a multi-tenancy isolation test (business A's data must not appear for business B).
4. Verify via Swagger and integration test.
5. Commit to Git at the feature level.

---

## Project Status

Phase 1 (Documentation) and Phase 2 (Synthetic Data Generator) are complete. Phase 3 (Hand-Trace Verification) is next. The project has 16 planned implementation phases in total — see [PROJECT_PLAN.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROJECT_PLAN.md).
