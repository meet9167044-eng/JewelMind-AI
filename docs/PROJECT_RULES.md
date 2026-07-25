# PROJECT_RULES.md

These rules exist to keep the architecture intact while using AI coding tools (Cursor/Codex) to vibe-code the implementation. They should be read by any AI coding tool before it touches this codebase, alongside PROJECT_DEFINITION.md and PROGRESS.md.

## Non-Negotiable Architectural Rules

1. Financial calculations must never be performed by the LLM.
2. All financial calculations must happen in deterministic Python or SQL functions.
3. AI may only explain verified analytics output — it must not invent, estimate, or "fill in" numbers.
4. PostgreSQL is the source of truth.
5. Backend business logic must not be placed inside frontend components.
6. Every analytics function must be testable in isolation.
7. Do not introduce new frameworks without a documented reason.
8. Never silently change the database schema — schema changes must be explicit and reflected in DATABASE_SCHEMA.md.
9. Always validate uploaded data before it reaches analytics or the database.
10. Keep modules independent (profit, inventory, metal, scenario engines should not have hidden cross-dependencies).

## Multi-Tenancy Rules (Non-Negotiable)

These rules are specific to the multi-business SaaS architecture introduced after Phase 2 documentation:

11. **Every analytics query must be filtered by `business_id`.** A query that aggregates across businesses is a critical data isolation bug.
12. **Every database table containing business data (products, purchases, sales, metal_rates) must include a `business_id` foreign key.** There are no exceptions.
13. **The `business_id` must be resolved server-side from the authenticated user's session or JWT token.** The frontend must never be trusted to supply `business_id` directly without server validation.
14. **Uploads are always tagged to the currently selected business** — the upload pipeline must inject `business_id` before persisting any row.
15. **The AI Copilot must only invoke analytics tools within the context of the current `business_id`.** Cross-business tool calls are forbidden.
16. **No API endpoint may return data from multiple businesses in a single response** unless it is the Business List endpoint (which returns only the businesses belonging to the authenticated user).

## Authentication & Metal Rates Service Rules

17. All API routes except `/health` and auth routes (`/auth/register`, `/auth/login`) require a valid JWT token.
18. JWT tokens encode the `user_id`. `business_id` is not stored in the JWT — it is passed per-request and validated server-side against the user's ownership.
19. Authentication must be built before any analytics endpoint is exposed.
20. **Metal rates must be automatically updated by a background Metal Rates Fetch Service via external commodity APIs.** Shopkeepers are never required to upload `metal_rates.csv` manually.
21. **Analytics and AI Copilot must always query stored rates from the PostgreSQL `metal_rates` table.** They must never invoke external APIs directly during calculations or query resolution.

## Tech Stack Discipline

Use the stack defined in PROJECT_DEFINITION.md / this documentation set and do not deviate mid-project. Specifically avoid adding, without a strong documented reason:

- MongoDB
- Firebase (unless genuinely necessary)
- Kubernetes
- A microservices split
- A vector database (until there is an actual retrieval need)

## Development Strategy

Never prompt an AI coding tool with an open-ended instruction like "Build my complete Jewellery BI Copilot." This produces large amounts of unreviewable code, inconsistent schemas, fake functionality, and hard-to-trace bugs.

Instead, follow this loop for every feature:

```
PLAN
 ↓
BUILD ONE FEATURE
 ↓
RUN IT
 ↓
TEST IT
 ↓
UNDERSTAND IT
 ↓
GIT COMMIT
 ↓
NEXT FEATURE
```

AI coding tools are a pair programmer, not an autonomous builder.

## How to Prompt AI Coding Tools

**Bad prompt:**
> Build inventory intelligence.

**Good prompt pattern:**
> Read: docs/PROJECT_DEFINITION.md, docs/DATABASE_SCHEMA.md, docs/PROJECT_RULES.md
>
> Implement only the [specific] service.
>
> Requirements:
> 1. Do not modify the database schema.
> 2. Do not modify frontend code (or: only modify frontend code, per scope).
> 3. All queries must filter by `business_id` — never aggregate across businesses.
> 4. [Specific functional requirements.]
> 5. Add unit tests.
> 6. Explain every file changed before implementation.

## Plan-Before-Code Rule

Always ask the AI coding tool to plan before writing code:

> Do not write code yet. First inspect the relevant files. Explain:
> 1. What currently exists.
> 2. What needs to change.
> 3. Which files will change.
> 4. Any risks.
> 5. Your implementation plan.
>
> Wait for approval before implementation.

## AI Copilot Guardrails (Runtime, Not Coding-Time)

These rules apply to the in-app AI Copilot's system prompt once Phase 13 (AI Copilot) is reached:

- Never invent financial values.
- Only use values returned by approved analytics tools.
- Clearly distinguish facts from suggestions.
- Do not claim certainty about future commodity prices.
- Do not call a mark-to-market movement a realized loss.
- If data is insufficient, say so explicitly.
- Always be able to show the evidence behind major conclusions.
- **Never reference data from a business other than the one currently selected by the user.**

## Git Discipline

Commit constantly, at the level of individual features, e.g.:

```
feat: setup FastAPI backend
feat: add business and user models
feat: add JWT authentication
feat: add business creation and selection
feat: add PostgreSQL models with business_id
feat: add synthetic dataset generator
feat: implement revenue analytics (scoped by business_id)
feat: implement profit diagnosis
feat: add inventory aging
feat: add metal exposure
feat: create dashboard
feat: add AI copilot
```

If an AI coding tool breaks something, `git revert` rather than trying to manually unwind AI-generated changes.

## Session Start Ritual

At the start of every new AI coding session, read (in this order) before doing anything:

1. PROJECT_DEFINITION.md
2. PROJECT_RULES.md
3. PROGRESS.md

This keeps long vibe-coding sessions anchored to the actual plan instead of drifting.

## The Golden Testing Principle

Every AI answer involving numbers should be traceable:

```
AI Statement
 ↓
Analytics Result
 ↓
Formula
 ↓
Database Rows (filtered by business_id)
```

Ideally surfaced in the UI as "Why?" → "View Evidence" → "View Data". This is what makes the project explainable AI rather than black-box AI.