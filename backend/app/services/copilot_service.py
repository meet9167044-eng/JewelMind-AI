"""
backend/app/services/copilot_service.py — AI Copilot Tool-Calling Layer
========================================================================
Architecture rules (AI_ARCHITECTURE.md):
    - The LLM NEVER sees or supplies business_id. It is injected server-side
      as a Python closure into every tool handler (Rule §1.2).
    - The Copilot makes ZERO external network calls. All numbers come from
      deterministic SQL/Pandas analytics functions (Phases 8-11).
    - The LLM only writes natural-language explanations; Python executes math.
    - Every response carries an 'evidence' object for the View Evidence trace.

LLM Provider: Google Gemini (configured via LLM_API_KEY + LLM_MODEL env vars).
Fail-Safe:    If LLM_API_KEY is not set, returns a clear setup message; the
              system never crashes — analytics pages stay fully operational.

Supported Tools (AI_ARCHITECTURE.md §2):
    1. analyze_profit_change     — 5-driver profit variance decomposition
    2. analyze_inventory         — Ageing, dead stock, slow movers, stockout
    3. analyze_metal_exposure    — WAR, net weight, valuation exposure
    4. simulate_metal_change     — Hypothetical rate-shift scenario
"""

import logging
import os
import time
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import settings, Settings as _Settings
from backend.app.services import (
    profit_diagnosis_service,
    inventory_service,
    metal_service,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model fallback chain — tried in order on quota / availability errors
# ---------------------------------------------------------------------------
_MODEL_FALLBACK_CHAIN = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]

# ---------------------------------------------------------------------------
# Retry helper — exponential back-off for 429 / RESOURCE_EXHAUSTED
# ---------------------------------------------------------------------------
_MAX_RETRIES   = 3          # total attempts per model
_RETRY_BASE_S  = 2          # seconds: 2 → 4 → 8


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()


def _generate_with_retry(client, model_name: str, contents, config):
    """
    Call client.models.generate_content with exponential back-off.
    Raises the last exception if all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            last_exc = exc
            if _is_quota_error(exc) and attempt < _MAX_RETRIES - 1:
                wait = _RETRY_BASE_S * (2 ** attempt)   # 2, 4, 8 …
                logger.warning(
                    "Quota hit on model '%s' (attempt %d/%d). Retrying in %ds…",
                    model_name, attempt + 1, _MAX_RETRIES, wait,
                )
                time.sleep(wait)
            else:
                raise
    raise last_exc  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────────────────
# System Prompt (AI_ARCHITECTURE.md §3 — 8 guardrails)
# ──────────────────────────────────────────────────────────────────────────────

def build_system_prompt(business_name: str) -> str:
    return f"""You are the JewelMind-AI Copilot, an expert analytics advisor for the jewellery business "{business_name}".

Your core mandate is to explain verified business analytics to the owner.

CRITICAL RULES:
1. NEVER CALCULATE OR INVENT NUMBERS. If you need to answer a financial query, invoke the appropriate tool.
2. ONLY USE NUMERIC VALUES returned in the tool response payloads. Never state a number not in the tool output.
3. CLEARLY SEPARATE FACT FROM HYPOTHESIS. Reference tool-verified drivers as facts. Frame suggestions as suggestions.
4. COMMODITY PRICES: Do not predict future gold/silver market movements. Frame simulated rate shifts strictly as "what-if scenarios."
5. VALUATION VS. LOSS: Always call inventory valuation drops "valuation exposure" or "unrealized paper adjustments." Never call them "realized losses" unless items have been melted and refined.
6. INCOMPLETE DATA: If the tool output is empty, say: "I do not have access to the dataset required to evaluate this question for {business_name}."
7. NEVER REFERENCE OTHER BUSINESSES. You are advising only the owner of {business_name}. Never mention or compare data from any other business.
8. NO EXTERNAL API CALLS. Never attempt to call external commodity APIs. Rely exclusively on stored database tool outputs.

Keep responses concise: 2-4 sentences for straightforward questions, up to 6 for multi-driver explanations. Always cite specific numbers from tool outputs."""


# ──────────────────────────────────────────────────────────────────────────────
# Tool Schemas (AI_ARCHITECTURE.md §2 — business_id NOT a parameter)
# ──────────────────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "analyze_profit_change",
        "description": "Decomposes profit differences (volume, discount, labor, mix, metal margin) between a baseline and target month for the current business.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_month":   {"type": "string", "description": "Month under review, format: YYYY-MM (e.g. '2026-06')."},
                "baseline_month": {"type": "string", "description": "Historical comparison month, format: YYYY-MM (e.g. '2026-05')."}
            },
            "required": ["target_month", "baseline_month"]
        }
    },
    {
        "name": "analyze_inventory",
        "description": "Returns inventory aging buckets, dead stock candidates, slow movers, and stockout warnings for the current business.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional category filter (e.g., 'chain', 'ring', 'payal')."}
            }
        }
    },
    {
        "name": "analyze_metal_exposure",
        "description": "Evaluates gold and silver net holdings, acquisition rate bases, today's board rates, and paper valuation exposure for the current business.",
        "parameters": {
            "type": "object",
            "properties": {
                "metal": {"type": "string", "enum": ["gold", "silver"], "description": "The precious metal to analyze."}
            },
            "required": ["metal"]
        }
    },
    {
        "name": "simulate_metal_change",
        "description": "Simulates financial impact of shifting metal prices by a specific percentage change for the current business.",
        "parameters": {
            "type": "object",
            "properties": {
                "metal":          {"type": "string", "enum": ["gold", "silver"], "description": "Target commodity metal."},
                "change_percent": {"type": "number", "description": "Percentage change, e.g., -10.0 for 10% decline, +15.0 for 15% rise."}
            },
            "required": ["metal", "change_percent"]
        }
    }
]


# ──────────────────────────────────────────────────────────────────────────────
# Tool Execution — business_id injected as closure; NEVER an LLM parameter
# ──────────────────────────────────────────────────────────────────────────────

def execute_tool(tool_name: str, params: dict, business_id: int, db: Session) -> dict[str, Any]:
    """
    Runs the named analytics tool, injecting business_id server-side.
    The LLM never sees business_id in tool schemas or tool call arguments.
    Returns: {tool, params, result, formula, source_tables, scoped_to_business_id}
    """
    try:
        if tool_name == "analyze_profit_change":
            tm = params.get("target_month", "")
            bm = params.get("baseline_month", "")
            ty, t_month = (int(x) for x in tm.split("-"))
            by, b_month = (int(x) for x in bm.split("-"))
            result = profit_diagnosis_service.analyze_profit_change(
                db, business_id, ty, t_month, by, b_month
            )
            return {
                "tool": tool_name, "params": {"target_month": tm, "baseline_month": bm},
                "result": result,
                "formula": "ΔProfit = Volume Effect + Discount Effect + Making Charge Effect + Product Mix Effect + Metal Margin Effect",
                "source_tables": ["purchases", "sales"],
                "scoped_to_business_id": business_id,
            }

        elif tool_name == "analyze_inventory":
            age  = inventory_service.calculate_inventory_age(db, business_id)
            perf = inventory_service.classify_inventory_performance(db, business_id)
            result = {**age, **perf}
            cat = params.get("category", "").strip().lower()
            if cat:
                for key in ("dead_stock", "slow_movers", "stockout_risks"):
                    result[key] = [i for i in result.get(key, []) if i.get("category") == cat]
            return {
                "tool": tool_name, "params": params, "result": result,
                "formula": "Dead Stock: age_days > 180 AND 0 sales in last 90d. Stockout Risk: coverage_days < 15",
                "source_tables": ["products", "purchases", "sales"],
                "scoped_to_business_id": business_id,
            }

        elif tool_name == "analyze_metal_exposure":
            metal  = params.get("metal", "gold")
            result = metal_service.calculate_metal_exposure(db, business_id, metal)
            return {
                "tool": tool_name, "params": {"metal": metal}, "result": result,
                "formula": "WAR = SUM(metal_cost) / SUM(net_weight_grams). Exposure = (market_rate - WAR) x net_weight",
                "source_tables": ["purchases", "sales", "metal_rates"],
                "scoped_to_business_id": business_id,
            }

        elif tool_name == "simulate_metal_change":
            metal  = params.get("metal", "gold")
            change = float(params.get("change_percent", 0.0))
            result = metal_service.simulate_metal_rate_shift(db, business_id, metal, change)
            return {
                "tool": tool_name, "params": {"metal": metal, "change_percent": change}, "result": result,
                "formula": "Simulated = (market_rate x (1 + delta%) - WAR) x net_weight. Delta = Simulated - Current Exposure",
                "source_tables": ["purchases", "sales", "metal_rates"],
                "scoped_to_business_id": business_id,
            }

        else:
            return {"tool": tool_name, "error": f"Unknown tool: {tool_name}", "result": {}}

    except Exception as exc:
        logger.error("Tool '%s' execution failed: %s", tool_name, exc)
        return {"tool": tool_name, "error": str(exc), "result": {}}


# ──────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ──────────────────────────────────────────────────────────────────────────────

def ask(
    question: str,
    business_id: int,
    business_name: str,
    db: Session,
) -> dict[str, Any]:
    """
    Main copilot function — powered by Groq (llama-3.3-70b-versatile).

    Flow:
      1. Build system prompt with business_name (not business_id — LLM never sees it).
      2. Send question + tool schemas to Groq (Round 1).
      3. If LLM returns a tool call → execute_tool() with business_id closure.
      4. Send tool result back to LLM (Round 2) → LLM writes explanation.
      5. Return {response_text, evidence}.

    Returns:
        {
            "response_text": str,       # Natural-language explanation
            "evidence":      dict|None  # View Evidence payload (formula + result)
        }
    """
    # Re-read .env on every request so key changes take effect without restart.
    _fresh = _Settings()
    api_key   = _fresh.llm_api_key.strip()
    model_name = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile").strip()

    if not api_key:
        return {
            "response_text": (
                "The AI Copilot requires an LLM API key. "
                "Add LLM_API_KEY=your_groq_key to your .env file. "
                "Get a free key at https://console.groq.com/keys"
            ),
            "evidence": None,
        }

    if db is None:
        from backend.app.database import SessionLocal
        db = SessionLocal()

    try:
        from groq import Groq

        client = Groq(api_key=api_key)

        # ── Build Groq-compatible tool schemas (OpenAI format) ───────────────
        groq_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in TOOL_DEFINITIONS
        ]

        system_msg = {"role": "system", "content": build_system_prompt(business_name)}
        user_msg   = {"role": "user",   "content": question}
        messages   = [system_msg, user_msg]

        # ── Round 1: LLM decides whether to call a tool ──────────────────────
        resp1 = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=groq_tools,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=1024,
        )

        choice1 = resp1.choices[0]

        # Direct text answer — no tool needed
        if choice1.finish_reason == "stop":
            return {
                "response_text": choice1.message.content.strip(),
                "evidence": None,
            }

        # Tool call requested
        if choice1.finish_reason != "tool_calls" or not choice1.message.tool_calls:
            return {
                "response_text": "I was unable to process your question. Please try rephrasing it.",
                "evidence": None,
            }

        tool_call = choice1.message.tool_calls[0]
        t_name    = tool_call.function.name
        import json
        t_args    = json.loads(tool_call.function.arguments or "{}")

        # Execute tool — business_id is a Python closure, NEVER from LLM
        evidence = execute_tool(t_name, t_args, business_id, db)

        # ── Round 2: send tool result, LLM writes natural-language explanation
        messages.append(choice1.message)           # assistant turn with tool_calls
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(evidence.get("result", {})),
        })

        resp2 = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
        )
        response_text = resp2.choices[0].message.content.strip()

        return {
            "response_text": response_text,
            "evidence":      evidence,
        }

    except ImportError:
        return {
            "response_text": "groq package is not installed. Run: pip install groq",
            "evidence": None,
        }
    except Exception as exc:
        logger.error("copilot_service.ask() failed: %s", exc, exc_info=True)
        err_msg = str(exc)
        if "401" in err_msg or "invalid_api_key" in err_msg.lower():
            msg = "Invalid Groq API key. Please check LLM_API_KEY in your .env file."
        elif "429" in err_msg or "rate_limit" in err_msg.lower():
            msg = "Groq rate limit hit. Please wait a moment and try again."
        else:
            msg = f"An error occurred while calling the AI Copilot: {err_msg[:200]}"
        return {
            "response_text": msg,
            "evidence": None,
        }


