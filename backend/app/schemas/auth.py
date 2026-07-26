"""
backend/app/schemas/auth.py — Pydantic Auth Schemas
=====================================================
Request and response models for the authentication endpoints.

These schemas are the contract between the API and its callers.
They perform input validation before any service logic runs.
"""

from pydantic import BaseModel, EmailStr, Field


# ── Request Schemas ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Body for POST /api/auth/register"""

    email: EmailStr = Field(
        ...,
        description="User's email address. Must be unique across all accounts.",
        examples=["meet@jewelmind.ai"],
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Plain-text password (min 8 characters). Never stored — bcrypt hash is saved.",
        examples=["SecurePass123"],
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's display name.",
        examples=["Meet Jain"],
    )


class LoginRequest(BaseModel):
    """Body for POST /api/auth/login"""

    email: EmailStr = Field(
        ...,
        description="Registered email address.",
        examples=["meet@jewelmind.ai"],
    )
    password: str = Field(
        ...,
        description="Plain-text password.",
        examples=["SecurePass123"],
    )


# ── Response Schemas ──────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """Returned by both /register and /login on success."""

    access_token: str = Field(
        ...,
        description="JWT access token. Include as 'Authorization: Bearer <token>' on protected routes.",
    )
    token_type: str = Field(default="bearer", description="Always 'bearer'.")
    user_id: int = Field(..., description="The authenticated user's ID.")
    full_name: str = Field(..., description="The authenticated user's display name.")
    email: str = Field(..., description="The authenticated user's email.")


class UserResponse(BaseModel):
    """Returned by GET /api/auth/me (the current user profile)."""

    user_id: int
    email: str
    full_name: str

    model_config = {"from_attributes": True}
