# PROJECT_DEFINITION.md

## Project

Jewellery BI Copilot

## Full Title

Jewellery BI Copilot: Explainable Analytics and Scenario Intelligence for Retail Jewellers

## One-Line Pitch

A multi-business SaaS platform where any retail jeweller can register, upload their own business data, and ask questions in plain English. The system mathematically analyzes profit, inventory, and precious-metal exposure per business, explains *why* things happened, simulates *what-if* scenarios, and recommends what deserves attention — while keeping every business's data completely private.

## Goal

Build a multi-tenant, multi-business analytics platform for retail jewellers. Each registered user manages one or more named businesses. All analytics are scoped to the currently selected business. Financial calculations are performed deterministically by Python and SQL. The AI Copilot only explains verified analytics output — it never calculates.

## Core Principle

```
DATA (per business)
 ↓
MATHEMATICS (scoped to business_id)
 ↓
ANALYSIS
 ↓
AI EXPLANATION
 ↓
DECISION SUPPORT
```

Python/SQL calculates all numbers. The AI only understands the question and explains the verified results. This principle governs the entire project and must never be violated (see PROJECT_RULES.md). **Every analytics query is filtered by `business_id` — no query may aggregate across businesses.**

## Architecture Tier

This is a **multi-business SaaS application**, not a single-dataset BI tool.

- Every user registers an account.
- A user creates one or more named jewellery businesses.
- All uploads, analytics, and Copilot queries operate on the currently selected business.
- No business can ever access another business's data.
- The design must be extensible: a single user owning multiple businesses is a supported use case.

## User Journey

```
Register / Log In
       ↓
Select or Create Business
       ↓
Upload Products CSV
       ↓
Upload Purchases CSV
       ↓
Upload Sales CSV
       ↓
System Automatically Keeps Metal Rates Updated (Background Scheduler)
       ↓
Dashboard (scoped to selected business)
       ↓
Analytics & AI Copilot (scoped to selected business)
       ↓
Scenario Simulator & Insights (scoped to selected business)
```

## Context / Motivation

- Real-world grounding comes from a family-owned jewellery shop, which surfaced a concrete pain point: precious-metal price volatility makes inventory valuation and sale timing hard to reason about (e.g., silver bought at a higher rate later being worth significantly less).
- This is a college final project — not a startup pursuit at this stage. No submission deadline. The goal is to build the fullest, most complete version of the idea for learning purposes, not a minimal scoped-down version.
- Being built solo by someone who can vibe-code (using AI coding tools like Cursor/Codex) and has partial coding ability — the plan is deliberately structured into small, understandable, testable stages rather than one large AI-generated dump.

## What We Are Building

A multi-tenant BI/analytics copilot for retail jewellers. Not operational software.

- Authentication (user registration & login)
- Business management (create/select a jewellery business)
- Per-business data upload (CSV/Excel ingestion)
- Per-business analytics (profit, inventory, metal exposure)
- AI Copilot (explains analytics, never calculates)
- Scenario Simulator (what-if analysis per business)
- Insights & Action Center (proactive alerts per business)

## What We Are NOT Building

Explicitly out of scope for this project:

- Billing software
- GST filing
- Accounting ERP
- Employee management
- Payroll
- Karigar (artisan) management
- CRM
- E-commerce
- Complete supplier management
- Multi-store ERP
- Gold-price prediction
- Blockchain
- Mobile app

Existing ERP systems already handle these operational functions. This project assumes such data can be exported/uploaded and focuses purely on analysis.

## Product Structure (Final, Not All Built at Once)

```
JEWELLERY BI COPILOT (Multi-Business SaaS)
├── 0. Auth (Register / Login)
├── 1. Business Hub (Create / Select Business)
├── 2. Dashboard / Command Center  [scoped to business]
├── 3. AI Copilot                  [scoped to business]
├── 4. Profit Intelligence         [scoped to business]
├── 5. Inventory Intelligence      [scoped to business]
├── 6. Metal Intelligence          [scoped to business]
├── 7. Scenario Simulator          [scoped to business]
├── 8. Insights / Action Center    [scoped to business]
└── 9. Data Upload                 [scoped to business]
```

## Module Summaries

### 0. Auth
User registration and login. JWT-based stateless authentication. Every API call after login carries the authenticated user's identity.

### 1. Business Hub
Post-login landing page. Shows the user's list of registered jewellery businesses. The user selects one (or creates a new one). The selected `business_id` is injected into every subsequent API request and analytics query.

### 2. Dashboard
Command center scoped to the selected business: revenue, gross profit, inventory value, ageing stock, top insights, and a natural-language "Ask Your Business" entry point.

### 3. AI Copilot
A chat interface that safely talks to the analytics engine via tool/function calling. Answers questions like "Why did profit fall?", "Where is my money stuck?", "What happens if silver drops 10%?" — always by calling deterministic tools scoped to the current `business_id`, never by inventing numbers.

### 4. Profit Intelligence
Revenue, gross profit, gross margin %, sales volume, average bill, discounts, making charges, category performance, monthly trends. Flagship feature: **Profit Diagnosis** — decomposes a profit change into quantified drivers (volume, discount, making-charge, product-mix effects).

### 5. Inventory Intelligence
Answers "Where is my money stuck?" via inventory ageing buckets, dead-stock candidates, slow movers, fast movers, stock coverage, and stockout risk.

### 6. Metal Intelligence
Analyzes gold/silver exposure: current inventory by metal, weighted acquisition rate, current reference valuation, and valuation exposure by category. Explicitly called "valuation exposure," never automatically "loss."

### 7. Scenario Simulator
User poses a hypothetical (e.g., "what if silver falls 10%?"); system calculates simulated valuation movement and identifies most-exposed categories. AI explains the scenario in plain language.

### 8. Insights / Action Center
Proactive, rule-based insights generated automatically from analytics refreshes (e.g., ageing stock alerts, discount-rate spikes, stockout risk). Uses cautious language (review / investigate / consider / potential) rather than absolute recommendations.

### 9. Data Upload & Automated Metal Rates
CSV/Excel upload scoped to the currently selected business for **Products**, **Purchases**, and **Sales**. Validates column schemas, data types, and constraints. Produces a Data Quality Report. Uploads are tagged with `business_id` — no cross-business data mixing is ever possible.

*Note on Metal Rates*: Shopkeepers are never required to upload metal rates manually. The system includes an automated **Metal Rates Service** driven by a background scheduler that periodically fetches Gold and Silver market rates from a trusted external commodity API and stores them in the global `metal_rates` table in MySQL. Historical `metal_rates.csv` is used ONLY for local development, testing, synthetic data generation, and demo database seeding. Production uses the automatic Metal Rate Fetch Service. Historical rates are retained indefinitely in MySQL for **valuation history**, **trend analysis**, and **scenario simulation**. If the external API is ever unavailable, the system logs the failure and continues using the latest stored rates without interrupting analytics or AI functionality.

## MVP Definition

The project is MVP-complete when this end-to-end flow works:

1. User registers, logs in, creates a business named "Rajesh Jewellers."
2. User uploads three CSV files: `Products.csv`, `Purchases.csv`, and `Sales.csv` for that business.
3. System background scheduler automatically fetches and validates latest Gold/Silver rates from external API and persists them into the global `metal_rates` database table.
4. Dashboard shows accurate metrics for that business only.
5. User asks "Why did profit fall in June?" → system correctly identifies causes → AI explains them with evidence (all filtered to this business).
6. User asks "Where is my money stuck?" → system shows slow/dead inventory for this business.
7. User asks "What if silver falls 10%?" → system calculates scenario impact for this business → AI explains exposure.

Everything beyond this flow (multi-business switching, ML anomaly detection, demand forecasting, further polish) is a bonus, not a requirement.

## Guiding Question for Scope Decisions

> Does this feature help answer WHAT happened, WHY it happened, WHAT IF something changes, or WHAT deserves attention — for a specific business?

If yes — consider it. If it's billing, GST, blockchain, marketplace, or similar — no, regardless of how appealing it sounds.

## Demo Narrative (Reference)

The final demo should be told as a story, not a feature tour: a jeweller ("Rajesh") logs in, creates his business, uploads his 3 store datasets (Products, Purchases, Sales) while the system automatically fetches current metal rates, sees profit fell 13% but doesn't know why. He asks the Copilot, sees quantified drivers with evidence, asks where capital is stuck, sees ageing/dead stock, then runs a silver-price scenario. Closing line: *"Traditional systems tell Rajesh what happened. Jewellery BI Copilot helps him understand why it happened, where the risks are, and what deserves attention next — for his business, and his business alone."*