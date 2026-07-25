# AI_ARCHITECTURE.md

## Core Design Principle: Non-Calculating & Isolated AI

The AI layer in **JewelMind-AI** has **zero** permission to execute mathematical calculations, estimate business metrics, or invoke external APIs directly.

Its role is to parse user intents, select and run deterministic internal tools that calculate metrics using Python and SQL against stored database tables, and translate the resulting data structures into readable explanation reports.

**Key Architecture Guardrails**:
- **Zero API Fetching**: AI never calls external commodity or market APIs. The **Metal Rate Fetch Service** is the ONLY component allowed to communicate with external metal-rate APIs.
- **Zero External Network Calls in AI/Analytics**: Neither the AI Copilot nor the Analytics Engine make external network calls.
- **Zero Calculation**: All financial calculations are executed by deterministic SQL/Pandas analytics functions.
- **Stored Data Source**: Analytics engines and tool handlers query stored metal rates from the MySQL database (`metal_rates` table).
- **Business Scoping**: In the multi-business SaaS architecture (implemented in Phase 14), the AI Copilot is always bound to a single `business_id`. Every tool call is automatically scoped to the currently selected business. Cross-business queries by the AI are architecturally impossible — the tool signatures do not accept a `business_id` argument because the server injects it from the authenticated session.
- **Environment Configuration**: LLM credentials and endpoint configuration are loaded via `LLM_API_KEY` per [PROJECT_PLAN.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/PROJECT_PLAN.md).

```
┌──────────────────────┐     ┌─────────────┐     ┌──────────────────────────┐
│ User Query           │────►│  LLM Agent  │────►│ Analytics Engine         │
│ "Why did GP fall?"   │     │ (Parses,    │     │ (Deterministic SQL       │
│ [business_id=1]      │◄────│  selects    │◄────│  queries stored DB rates)│
└──────────────────────┘     │  tool)      │     └──────────────────────────┘
                             └─────────────┘
```

---

## 1. Business Context & Session Flow

The Copilot receives the `business_id` from the server session layer — not from the user's chat message. The flow is:

```
User logs in → JWT issued (encodes user_id)
     ↓
User selects "Rajesh Jewellers" → business_id=1 stored in session
     ↓
User sends message to Copilot: "Why did profit fall?"
     ↓
Backend resolves business_id=1 from session
     ↓
Backend injects business_id=1 into every tool call
     ↓
Analytics engine executes SQL WHERE business_id = 1
     ↓
Tool returns verified payload → LLM writes explanation
```

The LLM never knows or sees the `business_id`. It receives the tool results scoped to the correct business and only writes the explanation.

---

## 2. Tool-Calling JSON Schemas

The LLM is configured with access to only four tools. No general database queries or open-ended code executions are allowed. `business_id` is **not** a tool parameter — it is injected server-side.

### Tool 1: `analyze_profit_change`
Decomposes profit variance between two monthly periods for the current business.

```json
{
  "name": "analyze_profit_change",
  "description": "Decomposes profit differences (volume, discount, labor, mix) between a baseline and target month for the current business.",
  "parameters": {
    "type": "object",
    "properties": {
      "target_month": {
        "type": "string",
        "description": "The month under review, format: YYYY-MM (e.g. '2026-06')."
      },
      "baseline_month": {
        "type": "string",
        "description": "The historical comparison month, format: YYYY-MM (e.g. '2026-05')."
      }
    },
    "required": ["target_month", "baseline_month"]
  }
}
```

### Tool 2: `analyze_inventory`
Retrieves inventory aging, fast/slow movers, dead stock, and stockout risks for the current business.

```json
{
  "name": "analyze_inventory",
  "description": "Returns inventory aging buckets, dead stock candidates, slow movers, and stockout warnings for the current business.",
  "parameters": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "description": "Optional category filter (e.g., 'chain', 'ring', 'payal')."
      }
    }
  }
}
```

### Tool 3: `analyze_metal_exposure`
Evaluates market price risk against Weighted Acquisition Rates for the current business.

```json
{
  "name": "analyze_metal_exposure",
  "description": "Evaluates gold and silver net holdings, acquisition rate bases, today's board rates, and paper valuation exposure for the current business.",
  "parameters": {
    "type": "object",
    "properties": {
      "metal": {
        "type": "string",
        "enum": ["gold", "silver"],
        "description": "The precious metal to analyze."
      }
    },
    "required": ["metal"]
  }
}
```

### Tool 4: `simulate_metal_change`
Simulates the impact of hypothetical commodity price changes for the current business.

```json
{
  "name": "simulate_metal_change",
  "description": "Simulates financial impact of shifting metal prices by a specific percentage change for the current business.",
  "parameters": {
    "type": "object",
    "properties": {
      "metal": {
        "type": "string",
        "enum": ["gold", "silver"],
        "description": "The target commodity metal."
      },
      "change_percent": {
        "type": "number",
        "description": "Percentage change value, e.g., -10.0 for 10% decline, +15.0 for 15% increase."
      }
    },
    "required": ["metal", "change_percent"]
  }
}
```

---

## 3. LLM System Prompt Guardrails

The system prompt is generated dynamically per request. It includes the authenticated business name (for context only — not for data access) and enforces strict behavioral rules.

```text
You are the JewelMind-AI Copilot, an expert analytics advisor for the jewellery business "{business_name}".

Your core mandate is to explain verified business analytics to the owner.

CRITICAL RULES:
1. NEVER CALCULATE OR INVENT NUMBERS. If you need to answer a financial query, you must invoke the appropriate tool from your tool list.
2. ONLY USE NUMERIC VALUES returned in the tool response payloads. If a number is not in the tool output, do not state it.
3. CLEARLY SEPARATE FACT FROM HYPOTHESIS. When stating drivers (e.g. volume drop), reference it as a verified fact from the calculation. When suggesting solutions, frame it as a suggestion, never an absolute directive.
4. COMMODITY PRICES: Do not predict future gold/silver market movements. Frame simulated rate shifts strictly as "what-if scenarios."
5. VALUATION VS. LOSS: Always call inventory valuation drops "valuation exposure" or "unrealized paper adjustments." Never call them "realized losses" unless the items have been melted and refined.
6. INCOMPLETE DATA: If the tool output is empty or missing expected parameters, say: "I do not have access to the dataset required to evaluate this question for {business_name}."
7. NEVER REFERENCE OTHER BUSINESSES. You are advising only the owner of {business_name}. Never mention or compare data from any other business.
8. NO EXTERNAL API CALLS. Never attempt to call external commodity APIs directly. Rely exclusively on stored database tool outputs provided by background rate services.
```

---

## 4. Explainability Trace (View Evidence)

Every AI response that references metrics must output an `evidence` object mapping the source of truth down to the database level.

```
AI Report ──► Tool Name & Parameters ──► Mathematical Formula ──► Source Table (filtered by business_id)
```

### UI Trace Interface
When the frontend renders a Copilot response, it checks for the `evidence` object:

1. **Trace Payload**: The backend returns the natural language string alongside the raw JSON output from the analytics engine in the `evidence` field.
2. **View Evidence Button**: The UI displays a `[View Evidence]` button next to each AI message.
3. **Drill-Down Modal**: Clicking the button opens a modal displaying:
   - **Calculation Log**: The mathematical formula from [ANALYTICS_FORMULAS.md](file:///c:/Users/MEET%20JAIN/JewelMind-AI/docs/ANALYTICS_FORMULAS.md) that was used.
   - **Data Aggregation**: A chart/table summarizing the matching SQL row aggregations that backed the tool output, annotated with the `business_id` they were scoped to.

This guarantees the system is **Explainable AI (XAI)** — every answer is fully traceable by the business owner.