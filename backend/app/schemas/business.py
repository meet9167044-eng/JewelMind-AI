"""
backend/app/schemas/business.py — Pydantic Business Schemas
============================================================
Request and response models for the business management endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ── Request Schemas ───────────────────────────────────────────────────────────

class CreateBusinessRequest(BaseModel):
    """Body for POST /api/businesses"""

    business_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="The trading name of the jewellery business.",
        examples=["Rajesh Jewellers"],
    )
    owner_name: str | None = Field(
        default=None,
        max_length=255,
        description="Contact person within the business.",
        examples=["Rajesh Mehta"],
    )
    email: str | None = Field(
        default=None,
        max_length=255,
        description="Business contact email address.",
        examples=["contact@rajeshjewellers.in"],
    )
    phone: str | None = Field(
        default=None,
        max_length=50,
        description="Business contact phone number.",
        examples=["+91-9876543210"],
    )


# ── Response Schemas ──────────────────────────────────────────────────────────

class BusinessResponse(BaseModel):
    """Returned for a single business."""

    business_id: int
    owner_user_id: int
    business_name: str
    owner_name: str | None
    email: str | None
    phone: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
