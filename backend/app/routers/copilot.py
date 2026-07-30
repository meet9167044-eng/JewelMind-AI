"""
backend/app/routers/copilot.py — AI Copilot API Endpoints
==========================================================
Routes:
    POST /api/businesses/{business_id}/copilot/ask

Security:
    - get_owned_business dependency enforces authentication AND business ownership.
    - business_id is resolved from route + JWT — never from request body or LLM.

Response schema (API_SPEC.md §8):
    {
        "response_text": str,    # Natural language answer from LLM
        "evidence": {            # View Evidence trace (present if a tool was called)
            "tool": str,         # Tool name that was called
            "params": dict,      # Tool parameters LLM chose
            "result": dict,      # Raw analytics result (deterministic)
            "formula": str,      # Mathematical formula used
            "source_tables": [], # DB tables queried
            "scoped_to_business_id": int
        } | None
    }
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.business import get_owned_business
from backend.app.models.business import Business
from backend.app.services import copilot_service

router = APIRouter(
    prefix="/api/businesses/{business_id}/copilot",
    tags=["AI Copilot"],
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Natural language question from the business owner.")


class AskResponse(BaseModel):
    response_text: str
    evidence: dict | None = None


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask the AI Copilot a business analytics question",
)
def ask_copilot(
    body: AskRequest,
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Accepts a natural-language question and returns an AI-generated explanation
    backed by deterministic analytics tools.

    **Security**: business_id is always resolved from the authenticated route
    parameter — never from the request body, and never visible to the LLM.

    **AI Architecture**:
    - The LLM selects and calls tools from a fixed set of 4 analytics functions.
    - Each tool handler is injected with business_id as a Python closure.
    - The LLM only writes natural language; all math is done in Python/SQL.
    - If LLM_API_KEY is not configured, returns a clear error message without crashing.
    """
    result = copilot_service.ask(
        question=body.question,
        business_id=business.business_id,   # Injected server-side — never from LLM
        business_name=business.business_name,
        db=db,
    )
    return AskResponse(**result)
