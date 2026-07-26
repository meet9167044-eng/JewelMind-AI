"""
backend/app/services/auth_service.py — Authentication Business Logic
======================================================================
Implements:
    hash_password(plain)           — bcrypt hashes a plain-text password
    verify_password(plain, hashed) — verifies a plain-text password against hash
    create_access_token(user_id)   — mints a HS256 JWT (30-day expiry by default)
    register(db, email, pwd, name) — creates and persists a new User
    login(db, email, password)     — authenticates credentials, returns User

Security rules enforced here:
    - Passwords are NEVER stored in plaintext.
    - JWTs contain only {"sub": str(user_id), "exp": ...} — no PII in the payload.
    - Duplicate email registrations are rejected with HTTP 409.
    - Wrong password returns HTTP 401 (same message as unknown email — no enumeration).
"""

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models.user import User

# ---------------------------------------------------------------------------
# Password hashing context (bcrypt)
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the given plain-text password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if the plain-text password matches the stored bcrypt hash."""
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(user_id: int) -> str:
    """
    Mint a signed HS256 JWT.

    Payload contains only:
        sub  — str(user_id)   [standard "subject" claim]
        exp  — UTC expiry timestamp

    The token does NOT include email, full_name, or any other PII.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_access_token_expire_days
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
def register(db: Session, email: str, password: str, full_name: str) -> User:
    """
    Create a new user account.

    Raises:
        ValueError("EMAIL_TAKEN") — if the email is already registered.
            Callers should map this to HTTP 409 Conflict.
    """
    existing = db.query(User).filter(User.email == email.lower().strip()).first()
    if existing:
        raise ValueError("EMAIL_TAKEN")

    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        full_name=full_name.strip(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def login(db: Session, email: str, password: str) -> User:
    """
    Authenticate with email + password.

    Raises:
        ValueError("INVALID_CREDENTIALS") — if the email is unknown OR the
            password is wrong. We deliberately use the same error message
            to prevent email-enumeration attacks.
            Callers should map this to HTTP 401 Unauthorized.
    """
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("INVALID_CREDENTIALS")
    return user
