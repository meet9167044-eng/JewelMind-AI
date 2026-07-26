"""
backend/app/services/business_service.py — Business Management Logic
=====================================================================
Implements:
    create_business(db, owner_user_id, data)  — persists a new Business row
    list_businesses(db, owner_user_id)         — returns all businesses for a user
    get_business_if_owner(db, business_id, owner_user_id)
                                               — returns Business or raises ValueError

Security rule enforced here:
    get_business_if_owner ALWAYS filters by BOTH business_id AND owner_user_id.
    This is the data-isolation gate. If a user does not own the requested
    business, the function raises ValueError("NOT_OWNER") — callers map
    this to HTTP 403 Forbidden.

    A query to the business-data tables (products, purchases, sales, analytics)
    is only allowed AFTER get_business_if_owner has validated ownership.
"""

from sqlalchemy.orm import Session

from backend.app.models.business import Business
from backend.app.schemas.business import CreateBusinessRequest


def create_business(
    db: Session,
    owner_user_id: int,
    data: CreateBusinessRequest,
) -> Business:
    """
    Create and persist a new jewellery business for the given user.

    A user may own multiple businesses. There is no uniqueness constraint
    on business_name — two users may both have a business called "Gold Palace".
    """
    business = Business(
        owner_user_id=owner_user_id,
        business_name=data.business_name.strip(),
        owner_name=data.owner_name.strip() if data.owner_name else None,
        email=data.email.strip() if data.email else None,
        phone=data.phone.strip() if data.phone else None,
    )
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


def list_businesses(db: Session, owner_user_id: int) -> list[Business]:
    """
    Return all businesses owned by the given user, ordered by creation date.

    Returns an empty list (not 404) if the user has no businesses yet.
    """
    return (
        db.query(Business)
        .filter(Business.owner_user_id == owner_user_id)
        .order_by(Business.created_at)
        .all()
    )


def get_business_if_owner(
    db: Session,
    business_id: int,
    owner_user_id: int,
) -> Business:
    """
    Return the Business if it exists AND is owned by owner_user_id.

    Raises:
        ValueError("NOT_OWNER") — if the business does not exist or
            belongs to a different user. Both cases produce the same
            error to prevent business_id enumeration attacks.
            Callers should map this to HTTP 403 Forbidden.
    """
    business = (
        db.query(Business)
        .filter(
            Business.business_id == business_id,
            Business.owner_user_id == owner_user_id,
        )
        .first()
    )
    if business is None:
        raise ValueError("NOT_OWNER")
    return business
