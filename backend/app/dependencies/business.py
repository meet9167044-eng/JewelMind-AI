"""
backend/app/dependencies/business.py — Business Ownership Dependency
=====================================================================
Provides `get_owned_business` — the most critical security dependency
in the entire JewelMind-AI application.

How it works:
    1. Reads `business_id` from the URL path parameter.
    2. Reads the authenticated `current_user` from the JWT dependency.
    3. Queries: SELECT * FROM businesses
                WHERE business_id = ? AND owner_user_id = current_user.user_id
    4. Returns the Business if found.
    5. Raises HTTP 403 Forbidden if not found (business doesn't exist
       OR belongs to a different user — same response to prevent enumeration).

Usage in any analytics / upload / copilot route:
    @router.get("/api/businesses/{business_id}/analytics/summary")
    def get_summary(
        business: Business = Depends(get_owned_business),
        db: Session = Depends(get_db),
    ):
        # business.business_id is guaranteed to be owned by the requester
        return analytics_service.summary(db, business.business_id)

This dependency MUST be applied to EVERY route that touches business data:
    products, purchases, sales, analytics, uploads, AI Copilot.

See PROJECT_RULES.md Rule 11: multi-tenancy data isolation.
"""

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.business import Business
from backend.app.models.user import User
from backend.app.services import business_service

_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Business not found or you do not have permission to access it.",
)


def get_owned_business(
    business_id: int = Path(..., description="The business to access.", ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Business:
    """
    FastAPI dependency — validate JWT and business ownership in one step.

    Raises HTTP 403 if:
        - The business_id does not exist.
        - The business exists but belongs to a different user.

    Both cases return the same 403 (prevents business_id enumeration).
    """
    try:
        return business_service.get_business_if_owner(
            db,
            business_id=business_id,
            owner_user_id=current_user.user_id,
        )
    except ValueError:
        raise _FORBIDDEN
