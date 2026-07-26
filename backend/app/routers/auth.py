"""
backend/app/routers/auth.py — Authentication Endpoints
========================================================
Routes:
    POST /api/auth/register  — create a new account (HTTP 201)
    POST /api/auth/login     — authenticate and get a JWT (HTTP 200)
    GET  /api/auth/me        — return current user profile (protected)

All routes are documented for Swagger UI automatically via FastAPI's
OpenAPI integration.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from backend.app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ── Register ──────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    response_description="JWT token and user metadata.",
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new JewelMind-AI account.

    - **email**: must be unique across all accounts.
    - **password**: minimum 8 characters (stored as bcrypt hash, never plaintext).
    - **full_name**: display name shown in the UI.

    Returns a JWT access token that can be used immediately.
    """
    try:
        user = auth_service.register(
            db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
        )
    except ValueError as exc:
        if str(exc) == "EMAIL_TAKEN":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )
        raise

    token = auth_service.create_access_token(user.user_id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login and get a JWT token",
    response_description="JWT token and user metadata.",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with email and password.

    Returns a JWT access token on success.
    Returns HTTP 401 for any invalid credentials (deliberate — prevents
    email enumeration attacks).
    """
    try:
        user = auth_service.login(db, email=payload.email, password=payload.password)
    except ValueError as exc:
        if str(exc) == "INVALID_CREDENTIALS":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise

    token = auth_service.create_access_token(user.user_id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
    )


# ── Me (protected) ────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user",
    response_description="Profile of the currently logged-in user.",
)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the profile of the currently authenticated user.

    Requires: `Authorization: Bearer <token>` header.
    """
    return current_user
