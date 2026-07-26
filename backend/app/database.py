"""
database.py — SQLAlchemy Database Session
==========================================
Provides:
    engine        — the SQLAlchemy Engine (MySQL via PyMySQL)
    SessionLocal  — a session factory used to open DB sessions
    Base          — declarative base class for all ORM models (added in Phase 7)
    get_db()      — FastAPI dependency that yields a DB session per request

Architecture note:
    Analytics queries ALWAYS read from this database — never from external APIs.
    The Metal Rate Fetch Service writes rates into the metal_rates table;
    analytics functions then read those stored rates.

    See docs/AI_ARCHITECTURE.md and docs/PROJECT_RULES.md (Rules 20-22).
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.database_url,
    # PyMySQL does not support async natively; we use sync SQLAlchemy here.
    # pool_pre_ping ensures stale connections are recycled automatically.
    pool_pre_ping=True,
    # Keep a small connection pool to avoid overwhelming the DB.
    pool_size=10,
    max_overflow=20,
    echo=False,   # Set True temporarily to debug SQL statements
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ---------------------------------------------------------------------------
# Declarative base — all ORM models will inherit from this (Phase 7)
# ---------------------------------------------------------------------------
Base = declarative_base()


# ---------------------------------------------------------------------------
# FastAPI dependency — yields one DB session per HTTP request
# ---------------------------------------------------------------------------
def get_db():
    """
    Yields a SQLAlchemy Session for the duration of a single HTTP request.
    The session is automatically closed when the request completes (even on error).

    Usage in a route:
        @router.get("/example")
        def example_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Health-check helper — used by GET /health
# ---------------------------------------------------------------------------
def check_db_connection() -> bool:
    """
    Returns True if a simple SELECT 1 query succeeds; False otherwise.
    Used by the /health endpoint to verify database reachability.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
