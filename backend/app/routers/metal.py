"""
backend/app/routers/metal.py — Metal Exposure & Scenario Endpoints
===================================================================
Routes:
    GET  /api/businesses/{business_id}/analytics/metal/rates
         Returns the latest stored metal rates (zero external calls).

    GET  /api/businesses/{business_id}/analytics/metal/exposure/{metal}
         Returns WAR + Valuation Exposure for gold or silver inventory.

    POST /api/businesses/{business_id}/analytics/metal/simulate/{metal}
         Simulates the impact of a rate shift (x%) on inventory valuation.

All routes are protected by `get_owned_business` dependency (authenticated
owner only). Multi-tenancy is enforced at the service layer.

Rule 21 (PROJECT_RULES.md): These endpoints NEVER make external API calls.
All rates come from the `metal_rates` MySQL table.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.business import get_owned_business
from backend.app.models.business import Business
from backend.app.services import metal_service

router = APIRouter(
    prefix="/api/businesses/{business_id}/analytics/metal",
    tags=["Metal Exposure"],
)


@router.get(
    "/rates",
    summary="Latest stored metal rates (no external call)",
)
def get_metal_rates(
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Returns the most recently stored gold and silver rates from MySQL.
    These rates are populated by the background Metal Rate Fetch Service.
    This endpoint makes ZERO external API calls (Rule 21).
    """
    return metal_service.get_latest_metal_rates(db)


@router.get(
    "/exposure/{metal}",
    summary="Weighted Acquisition Rate & Valuation Exposure for active inventory",
)
def get_metal_exposure(
    metal: metal_service.MetalType,
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Computes valuation risk for active inventory of the specified metal.

    **Weighted Acquisition Rate (WAR)** — §4.A:
        WAR = SUM(metal_cost) / SUM(net_weight)

    **Valuation Exposure** — §4.B:
        SUM( net_weight × (R_today × purity_ratio − WAR) )

    A positive exposure means inventory is currently worth more than its
    acquisition cost at market rates. Negative means below cost.

    Uses only stored DB rates — zero external network calls (Rule 21).
    """
    return metal_service.calculate_metal_exposure(
        db, business_id=business.business_id, metal=metal
    )


@router.get(
    "/simulate/{metal}",
    summary="Scenario simulation: impact of a metal rate shift on inventory valuation",
)
def simulate_rate_shift(
    metal: metal_service.MetalType,
    change_percent: float = Query(
        ...,
        description="Percentage rate change. Negative = price drop (e.g. -10). Positive = rise.",
        ge=-100.0,
        le=200.0,
    ),
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Simulates the paper valuation impact if the metal price shifts by `change_percent`.

    **Simulated Rate** — §5.A:
        R_sim = R_today × (1 + change_percent/100)

    **Delta Value** — §5.C:
        Δ = Simulated Exposure − Current Exposure

    All calculations use stored DB rates only — zero external calls (Rule 21).
    """
    return metal_service.simulate_metal_rate_shift(
        db,
        business_id=business.business_id,
        metal=metal,
        change_percent=change_percent,
    )
