"""
backend/app/services/scheduler.py — Background Metal Rate Scheduler
===================================================================
APScheduler background job that periodically invokes the Metal Rate
Fetch Service to keep the `metal_rates` table up to date.

Architecture rules (PROJECT_RULES.md §Rule 22):
    - Runs as a background daemon — never blocks the API server.
    - On fetch failure: logs warning, does NOT raise, does NOT stop the job.
    - On success: persists today's gold_24k, gold_22k, silver rates to MySQL.

Configuration (via .env):
    METAL_RATE_REFRESH_INTERVAL — seconds between fetches (default: 86400 = 24h)

Integration with FastAPI:
    - Call `start_scheduler(db_session_factory)` in the FastAPI `lifespan` event.
    - Call `stop_scheduler()` on shutdown.

The scheduler runs a BackgroundScheduler (APScheduler 3.x) with an
IntervalTrigger. It intentionally uses a simple interval (not cron) so
that the first fetch fires after the interval expires, preventing a noisy
network call during server startup in CI/test environments.
"""

import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.app.config import settings
from backend.app.services.metal_rate_fetcher import fetch_and_store_today

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _fetch_job(db_session_factory: Callable) -> None:
    """
    The scheduled job function.
    Wraps fetch_and_store_today() so APScheduler can call it
    without arguments (APScheduler 3.x does not support partial easily).
    """
    logger.info("Scheduled metal rate fetch starting ...")
    ok = fetch_and_store_today(db_session_factory)
    if ok:
        logger.info("Scheduled metal rate fetch completed successfully.")
    else:
        logger.warning(
            "Scheduled metal rate fetch failed — analytics continues "
            "using the latest stored rates in MySQL."
        )


def start_scheduler(db_session_factory: Callable) -> None:
    """
    Starts the APScheduler background scheduler.
    Safe to call multiple times — a running scheduler is not restarted.

    Parameters:
        db_session_factory — callable returning a SQLAlchemy Session
                             (pass `backend.app.database.SessionLocal`)
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.debug("Scheduler already running — skipping start.")
        return

    interval_seconds = int(settings.metal_rate_refresh_interval)
    logger.info(
        "Starting metal rate scheduler (interval: %ds / %.1fh)",
        interval_seconds, interval_seconds / 3600,
    )

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        func=_fetch_job,
        trigger=IntervalTrigger(seconds=interval_seconds),
        args=[db_session_factory],
        id="metal_rate_fetch",
        name="Metal Rate Fetch Service",
        replace_existing=True,
        max_instances=1,          # prevent overlapping fetches
        coalesce=True,            # merge missed runs
        misfire_grace_time=600,   # allow up to 10 min late
    )
    _scheduler.start()
    logger.info("Metal rate scheduler started.")


def stop_scheduler() -> None:
    """Gracefully shuts down the scheduler on application shutdown."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Metal rate scheduler stopped.")
    _scheduler = None


def get_scheduler() -> BackgroundScheduler | None:
    """Returns the current scheduler instance (for health checks / testing)."""
    return _scheduler
