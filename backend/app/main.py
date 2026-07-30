"""
main.py — FastAPI Application Entry Point
==========================================
Phase 4 skeleton. Contains ONLY:
    - Application factory
    - CORS middleware
    - GET /health endpoint (checks DB connectivity)

No routes, models, or business logic yet.
Those are added phase-by-phase from Phase 5 onward.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.database import check_db_connection, SessionLocal
from backend.app.routers import auth as auth_router
from backend.app.routers import businesses as businesses_router
from backend.app.routers import analytics as analytics_router
from backend.app.routers import metal as metal_router
from backend.app.routers import upload as upload_router
from backend.app.routers import copilot as copilot_router
from backend.app.services import scheduler as scheduler_service


# ---------------------------------------------------------------------------
# Lifespan: start / stop background scheduler
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan event handler.
    - Startup:  starts the metal rate background scheduler.
    - Shutdown: gracefully stops the scheduler.
    """
    scheduler_service.start_scheduler(SessionLocal)
    yield
    scheduler_service.stop_scheduler()


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="JewelMind-AI",
    description=(
        "Explainable Analytics and Scenario Intelligence for Retail Jewellers. "
        "Multi-business SaaS platform — every analytics query is scoped to a "
        "single business_id. The AI Copilot only explains verified analytics "
        "output; it never calculates."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# Allow the Next.js frontend (Phase 13) to communicate with this API.
# In production, replace "*" with the actual deployed frontend origin.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Tighten to specific origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(businesses_router.router)
app.include_router(analytics_router.router)
app.include_router(metal_router.router)
app.include_router(upload_router.router)
app.include_router(copilot_router.router)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    tags=["Health"],
    summary="Application health check",
    response_description="Returns ok if the server and database are reachable.",
)
def health_check():
    """
    Returns the operational status of the application.

    - **status**: "ok" if everything is healthy; "degraded" if the DB is unreachable.
    - **database**: true if the MySQL connection succeeds; false otherwise.

    This endpoint does NOT require authentication and is safe to call from
    load-balancer probes.
    """
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "version": "0.1.0",
    }
