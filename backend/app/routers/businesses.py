"""
backend/app/routers/businesses.py — Business Management Endpoints
=================================================================
Routes:
    GET  /api/businesses                     — list all businesses for current user
    POST /api/businesses                     — create a new business
    GET  /api/businesses/{business_id}       — get single business (ownership enforced)

All routes require JWT authentication via get_current_user.
The single-business GET also enforces ownership via get_owned_business.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.dependencies.business import get_owned_business
from backend.app.models.business import Business
from backend.app.models.user import User
from backend.app.schemas.business import BusinessResponse, CreateBusinessRequest
from backend.app.services import business_service

router = APIRouter(prefix="/api/businesses", tags=["Businesses"])


# ── List businesses ───────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[BusinessResponse],
    status_code=status.HTTP_200_OK,
    summary="List all businesses owned by the current user",
)
def list_businesses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns all jewellery businesses owned by the authenticated user.
    Returns an empty list if the user has not created any businesses yet.
    """
    return business_service.list_businesses(db, owner_user_id=current_user.user_id)


# ── Create business ───────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=BusinessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new jewellery business",
)
def create_business(
    payload: CreateBusinessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new jewellery business under the authenticated user's account.

    - **business_name**: required. E.g. "Rajesh Jewellers".
    - **owner_name**, **email**, **phone**: optional contact details.

    Returns the newly created business including its `business_id`.
    This `business_id` must be used in all subsequent analytics requests.
    """
    return business_service.create_business(
        db,
        owner_user_id=current_user.user_id,
        data=payload,
    )


# ── Get single business ───────────────────────────────────────────────────────

@router.get(
    "/{business_id}",
    response_model=BusinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a business by ID (ownership enforced)",
)
def get_business(
    business: Business = Depends(get_owned_business),
):
    """
    Returns a single business by its ID.

    - Requires JWT authentication.
    - Returns **HTTP 403** if the business does not exist or belongs to
      another user (ownership is validated by `get_owned_business`).
    """
    return business
