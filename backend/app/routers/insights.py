"""
backend/app/routers/insights.py — Action Center & Proactive Insights API
=========================================================================
Routes:
    GET /api/businesses/{business_id}/insights

Security:
    - get_owned_business dependency enforces authentication AND ownership.
    - business_id resolved from route + JWT — never from query params.

Response schema:
    {
        "business_id": int,
        "as_of":       str (ISO date),
        "count":       int,
        "alerts": [
            {
                "rule_id":    str,
                "priority":   "high" | "medium" | "low",
                "title":      str,
                "detail":     str,
                "action_link": str,
                "evidence":   dict
            }
        ]
    }
"""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.business import get_owned_business
from backend.app.models.business import Business
from backend.app.services import insight_service

router = APIRouter(
    prefix="/api/businesses/{business_id}/insights",
    tags=["Action Center"],
)


class AlertItem(BaseModel):
    rule_id:     str
    priority:    str
    title:       str
    detail:      str
    action_link: str
    evidence:    dict


class InsightsResponse(BaseModel):
    business_id: int
    as_of:       str
    count:       int
    alerts:      list[AlertItem]


@router.get(
    "",
    response_model=InsightsResponse,
    summary="Get proactive business insights & action alerts",
)
def get_insights(
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Runs the rule-based Insight Engine for the authenticated user's business
    and returns a prioritised list of action alerts.

    **Rules Evaluated**:
    - **High**: Aged Inventory > 180 days with total acquisition cost > ₹1L.
    - **Medium**: Stockout risk — fast-moving products with < 15 days of coverage.
    - **Low**: Discount rate escalation > 25% month-over-month.

    All rules are strictly scoped to `business_id`. No cross-business data leakage
    is possible because every underlying analytics function enforces `business_id`.
    """
    alerts = insight_service.run_all_rules(db, business.business_id)
    return InsightsResponse(
        business_id=business.business_id,
        as_of=str(date.today()),
        count=len(alerts),
        alerts=[AlertItem(**a) for a in alerts],
    )
