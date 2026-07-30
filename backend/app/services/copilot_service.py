"""
backend/app/services/copilot_service.py — AI Copilot Tool-Calling Layer
========================================================================
Architecture rules (AI_ARCHITECTURE.md):
    - The LLM NEVER sees or supplies business_id. It is injected server-side
      as a closure into every tool handler.
    - The Copilot makes ZERO external network calls. All numbers come from
      deterministic SQL/Pandas analytics functions (Phases 8-11).
    - The LLM only writes explanations; Python executes the math.
    - Every response carries an 'evidence' object for the View Evidence trace.

LLM Provider: Google Gemini (configurable via LLM_API_KEY + LLM_MODEL env vars).
Fallback:     If LLM_API_KEY is not set, service returns a clear setup message.

Supported Tools (AI_ARCHITECTURE.md §2):
    1. analyze_profit_change     — 5-driver profit variance decomposition
    2. analyze_inventory         — Ageing, dead stock, slow movers, stockout
    3. analyze_metal_exposure    — WAR, net weight, valuation exposure
    4. simulate_metal_change     — Hypothetical rate-shift scenario
"""

import json
import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from backend.app.services import analytics_service, inventory_service, metal_service

logger = logging.getLogger(__name__)

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL   = os.getenv("LLM_MODEL", "gemini-2.0-flash")

# ──────────────────────────────────────────────────────────────────────────────
# System Prompt (AI_ARCHITECTURE.md §3 — 8 guardrails)
# ──────────────────────────────────────────────────────────────────────────────

def build_system_prompt(business_name: str) -> str:
    return f"""You are the JewelMind-AI Copilot, an expert analytics advisor for the jewellery business "{business_name}".

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

Keep responses concise but informative — 2-4 sentences for straightforward questions, up to 6 for multi-driver explanations. Always reference specific numbers from tool outputs."""


# ──────────────────────────────────────────────────────────────────────────────
# Tool Schemas (AI_ARCHITECTURE.md §2 — business_id NOT a parameter)
# ──────────────────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "analyze_profit_change",
        "description": (
            "Decomposes profit differences (volume, discount, labor, mix, metal margin) "
            "between a baseline and target month for the current business."
        ),
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
    },
    {
        "name": "analyze_inventory",
        "description": (
            "Returns inventory aging buckets, dead stock candidates, slow movers, "
            "and stockout warnings for the current business."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter (e.g., 'chain', 'ring', 'payal')."
                }
            }
        }
    },
    {
        "name": "analyze_metal_exposure",
        "description": (
            "Evaluates gold and silver net holdings, acquisition rate bases, "
            "today's board rates, and paper valuation exposure for the current business."
        ),
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
    },
    {
        "name": "simulate_metal_change",
        "description": (
            "Simulates financial impact of shifting metal prices by a specific percentage "
            "change for the current business."
        ),
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
                    "description": "Percentage change, e.g., -10.0 for 10% decline, +15.0 for 15% increase."
                }
            },
            "required": ["metal", "change_percent"]
        }
    }
]


# ──────────────────────────────────────────────────────────────────────────────
# Tool Execution (business_id injected as closure — never an LLM parameter)
# ──────────────────────────────────────────────────────────────────────────────

def execute_tool(tool_name: str, params: dict, business_id: int, db: Session) -> dict[str, Any]:
    """
    Executes the named analytics tool, injecting business_id server-side.
    Returns a dict with 'result' (structured data) and 'formula' (for View Evidence).
    The LLM never sees business_id in the tool schema or the tool call.
    """
    try:
        if tool_name == "analyze_profit_change":
            target  = params.get("target_month", "")
            baseline = params.get("baseline_month", "")
            ty, tm  = (int(x) for x in target.split("-"))
            by, bm  = (int(x) for x in baseline.split("-"))
            result = analytics_service.calculate_profit_diagnosis(
                db, business_id, ty, tm, by, bm
            )
            return {
                "tool": tool_name,
                "params": {"target_month": target, "baseline_month": baseline},
                "result": result,
                "formula": "ΔProfit = Volume + Discount + Making Charge + Product Mix + Metal Margin effects",
                "source_tables": ["purchases", "sales"],
                "scoped_to_business_id": business_id,
            }

        elif tool_name == "analyze_inventory":
            age  = inventory_service.calculate_inventory_age(db, business_id)
            perf = inventory_service.classify_inventory_performance(db, business_id)
            result = {**age, **perf}
            if params.get("category"):
                cat = params["category"].lower()
                result["dead_stock"]     = [i for i in result.get("dead_stock",     []) if i.get("category") == cat]
                result["slow_movers"]    = [i for i in result.get("slow_movers",    []) if i.get("category") == cat]
                result["stockout_risks"] = [i for i in result.get("stockout_risks", []) if i.get("category") == cat]
            return {
                "tool": tool_name,
                "params": params,
                "result": result,
                "formula": "Dead Stock: age_days > 180 AND no sales in last 90d. Stockout Risk: stock_coverage_days < 15",
                "source_tables": ["products", "purchases", "sales"],
                "scoped_to_business_id": business_id,
            }

        elif tool_name == "analyze_metal_exposure":
            metal = params.get("metal", "gold")
            result = metal_service.calculate_exposure(db, business_id, metal)
            return {
                "tool": tool_name,
                "params": {"metal": metal},
                "result": result,
                "formula": "WAR = SUM(metal_cost) / SUM(net_weight). Exposure = (market_rate - WAR) × net_weight",
                "source_tables": ["purchases", "sales", "metal_rates"],
                "scoped_to_business_id": business_id,
            }

        elif tool_name == "simulate_metal_change":
            metal  = params.get("metal", "gold")
            change = float(params.get("change_percent", 0))
            result = metal_service.simulate_rate_change(db, business_id, metal, change)
            return {
                "tool": tool_name,
                "params": {"metal": metal, "change_percent": change},
                "result": result,
                "formula": "Simulated Exposure = (market_rate × (1 + Δ%) − WAR) × net_weight. Delta = Simulated − Current",
                "source_tables": ["purchases", "sales", "metal_rates"],
                "scoped_to_business_id": business_id,
            }

        else:
            return {"tool": tool_name, "error": f"Unknown tool: {tool_name}", "result": {}}

    except Exception as exc:
        logger.error("Tool '%s' failed: %s", tool_name, exc)
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
    Main copilot function. Sends question to LLM, handles tool calls, returns:
        {
            "response_text": str,       # Natural language explanation
            "evidence": dict | None,    # View Evidence payload (tool + result + formula)
        }

    business_id is NEVER sent to the LLM — it is injected into tool handlers as
    a Python closure (AI_ARCHITECTURE.md).
    """
    if not LLM_API_KEY:
        return {
            "response_text": (
                "The AI Copilot is not configured yet. "
                "Please set LLM_API_KEY in your .env file to enable AI-powered analytics. "
                "All analytics pages remain fully functional."
            ),
            "evidence": None,
        }

    try:
        import google.generativeai as genai
        genai.configure(api_key=LLM_API_KEY)

        # Convert our tool schemas to Gemini-compatible format
        from google.generativeai.types import FunctionDeclaration, Tool as GeminiTool

        gemini_tools = GeminiTool(
            function_declarations=[
                FunctionDeclaration(**t) for t in TOOL_DEFINITIONS
            ]
        )

        model = genai.GenerativeModel(
            model_name=LLM_MODEL,
            system_instruction=build_system_prompt(business_name),
            tools=[gemini_tools],
        )

        # ── Round 1: LLM may respond or call a tool ──────────────────────────
        chat   = model.start_chat()
        resp_1 = chat.send_message(question)
        part_1 = resp_1.candidates[0].content.parts[0]

        # Direct text answer (no tool call needed)
        if hasattr(part_1, "text"):
            return {"response_text": part_1.text, "evidence": None}

        # Tool call detected
        if not hasattr(part_1, "function_call"):
            return {"response_text": "I was unable to process your question. Please try rephrasing.", "evidence": None}

        fn_call = part_1.function_call
        tool_name = fn_call.name
        tool_params = dict(fn_call.args)  # dict from Gemini proto

        # ── Execute tool (business_id injected here — Rule §1.2) ─────────────
        evidence = execute_tool(tool_name, tool_params, business_id, db)

        # ── Round 2: LLM writes explanation from tool result ──────────────────
        import google.protobuf.struct_pb2 as struct_pb2
        from google.generativeai.types import content_types

        tool_response = {
            k: v for k, v in evidence.get("result", {}).items()
            if v is not None
        }

        resp_2 = chat.send_message(
            content_types.to_contents({
                "role": "tool",
                "parts": [{
                    "function_response": {
                        "name": tool_name,
                        "response": tool_response,
                    }
                }]
            })
        )

        response_text = resp_2.candidates[0].content.parts[0].text

        return {
            "response_text": response_text,
            "evidence": evidence,
        }

    except ImportError:
        return {
            "response_text": "google-generativeai package is not installed. Run: pip install google-generativeai",
            "evidence": None,
        }
    except Exception as exc:
        logger.error("Copilot ask() failed: %s", exc, exc_info=True)
        return {
            "response_text": (
                f"I encountered an error while analyzing your question. "
                f"Please verify your LLM_API_KEY and try again. (Error: {type(exc).__name__})"
            ),
            "evidence": None,
        }
