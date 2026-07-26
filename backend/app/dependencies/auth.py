"""
backend/app/dependencies/auth.py — JWT Auth Dependency
=========================================================
Provides `get_current_user` — a FastAPI dependency that:
    1. Extracts the Bearer token from the Authorization header.
    2. Decodes and validates the JWT.
    3. Loads the User from the database.
    4. Returns the authenticated User object.

This dependency is injected into EVERY protected route (Phase 5 onward).
The business-scoping dependency (`get_owned_business`) builds on top of
this in Phase 6.

Usage in a route:
    @router.get("/protected")
    def some_route(current_user: User = Depends(get_current_user)):
        ...
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.user import User

# HTTPBearer extracts the "Authorization: Bearer <token>" header automatically.
_bearer_scheme = HTTPBearer(auto_error=True)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — decode JWT and return the authenticated User.

    Raises HTTP 401 if:
        - The token is missing, expired, or has an invalid signature.
        - The user_id inside the token does not match any database record.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise _CREDENTIALS_EXCEPTION
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise _CREDENTIALS_EXCEPTION

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise _CREDENTIALS_EXCEPTION

    return user
