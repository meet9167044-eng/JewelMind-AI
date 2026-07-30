"""
backend/app/services/metal_rate_fetcher.py
==========================================
External Commodity API Integration with Provider Abstraction.

Architecture rules (PROJECT_RULES.md §Rules 20-22):
    - This is the ONLY component in the system allowed to communicate with
      external metal-rate APIs.
    - Analytics Engine and AI Copilot MUST NEVER call external APIs.
    - Provider is fully configurable via environment variables:
        METAL_RATE_API_PROVIDER  (default: "GoldAPI")
        METAL_RATE_API_KEY
        METAL_RATE_API_URL
    - If the external API is unavailable, the scheduler logs the failure,
      continues using the latest stored rates from MySQL, and NEVER interrupts
      analytics or AI functionality.

Provider Interface:
    Every provider must implement `AbstractMetalRateProvider` and return a
    `FetchedRates` dataclass. Adding a new provider requires:
        1. Create a subclass of `AbstractMetalRateProvider`.
        2. Register it in `_PROVIDERS`.
    Analytics logic never changes when providers are swapped.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

@dataclass
class FetchedRates:
    """
    Rates fetched from an external provider for a single calendar day.
    All values are INR per gram.
    """
    rate_date: date
    gold_24k:  float   # INR per gram, 24-karat gold
    gold_22k:  float   # INR per gram, 22-karat gold
    silver:    float   # INR per gram, 999 fine silver


# ---------------------------------------------------------------------------
# Abstract provider interface
# ---------------------------------------------------------------------------

class AbstractMetalRateProvider(ABC):
    """
    All external rate providers must implement this interface.
    Analytics logic only ever calls `fetch_today()` — never the provider
    implementation directly.
    """

    @abstractmethod
    def fetch_today(self) -> FetchedRates:
        """
        Fetch today's metal rates from the external source.
        Must raise an exception if the fetch fails (caller handles fallback).
        """
        ...


# ---------------------------------------------------------------------------
# GoldAPI provider (default)
# Reference: https://www.goldapi.io/api (configured via METAL_RATE_API_KEY)
# ---------------------------------------------------------------------------

GOLD_API_PURITY_RATIO_22K = 22 / 24   # ≈ 0.9167

class GoldAPIProvider(AbstractMetalRateProvider):
    """
    Fetches gold and silver rates from goldapi.io.
    Endpoint: GET {api_url}/{symbol}/INR
    Header:   x-access-token: {api_key}

    Symbols used:
        XAU — Gold  (troy-ounce price; convert to per-gram)
        XAG — Silver (troy-ounce price; convert to per-gram)

    1 troy ounce = 31.1035 grams
    """

    TROY_OZ_TO_GRAMS = 31.1035

    def __init__(self) -> None:
        self.api_url = settings.metal_rate_api_url.rstrip("/")
        self.api_key = settings.metal_rate_api_key

    def _fetch_symbol(self, symbol: str) -> dict:
        url = f"{self.api_url}/{symbol}/INR"
        headers = {
            "x-access-token": self.api_key,
            "Content-Type":   "application/json",
        }
        response = httpx.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()
        return response.json()

    def fetch_today(self) -> FetchedRates:
        gold_data   = self._fetch_symbol("XAU")
        silver_data = self._fetch_symbol("XAG")

        # goldapi returns price in INR per troy ounce
        gold_24k_per_gram  = float(gold_data["price"]) / self.TROY_OZ_TO_GRAMS
        gold_22k_per_gram  = gold_24k_per_gram * GOLD_API_PURITY_RATIO_22K
        silver_per_gram    = float(silver_data["price"]) / self.TROY_OZ_TO_GRAMS

        if gold_24k_per_gram <= 0 or silver_per_gram <= 0:
            raise ValueError(
                f"Non-positive rates received from GoldAPI: "
                f"gold_24k={gold_24k_per_gram}, silver={silver_per_gram}"
            )

        return FetchedRates(
            rate_date=date.today(),
            gold_24k =round(gold_24k_per_gram, 2),
            gold_22k =round(gold_22k_per_gram, 2),
            silver   =round(silver_per_gram,   2),
        )


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, type[AbstractMetalRateProvider]] = {
    "goldapi": GoldAPIProvider,
}


def get_provider() -> AbstractMetalRateProvider:
    """
    Returns the configured provider instance.
    Provider name is read from METAL_RATE_API_PROVIDER (case-insensitive).
    Raises ValueError if the configured provider is not registered.
    """
    name = settings.metal_rate_api_provider.lower()
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise ValueError(
            f"Unknown metal rate provider '{name}'. "
            f"Registered: {list(_PROVIDERS.keys())}"
        )
    return provider_cls()


# ---------------------------------------------------------------------------
# Public: fetch and persist today's rates
# ---------------------------------------------------------------------------

def fetch_and_store_today(db_session_factory) -> bool:
    """
    Fetches today's metal rates from the configured external provider and
    persists them to the `metal_rates` table (upsert by rate_date).

    Parameters:
        db_session_factory — callable that returns a SQLAlchemy Session

    Returns:
        True  — rates fetched and stored successfully
        False — fetch failed; latest stored rates remain in DB (fail-safe)

    Rule 22 fail-safe: on any error, logs warning and returns False.
    The scheduler continues running; analytics uses stored rates.
    """
    from backend.app.models.metal_rate import MetalRate  # avoid circular import

    try:
        provider = get_provider()
        rates    = provider.fetch_today()
        logger.info(
            "Metal rates fetched [%s]: gold_24k=%.2f, gold_22k=%.2f, silver=%.2f",
            rates.rate_date, rates.gold_24k, rates.gold_22k, rates.silver,
        )
    except Exception as exc:
        # Rule 22: log failure, never interrupt analytics
        logger.warning("Metal rate fetch FAILED — using latest stored rates. Error: %s", exc)
        return False

    db = db_session_factory()
    try:
        existing = db.query(MetalRate).filter(MetalRate.rate_date == rates.rate_date).first()
        if existing:
            existing.gold_24k = rates.gold_24k
            existing.gold_22k = rates.gold_22k
            existing.silver   = rates.silver
            logger.info("Updated existing metal_rates row for %s", rates.rate_date)
        else:
            db.add(MetalRate(
                rate_date=rates.rate_date,
                gold_24k =rates.gold_24k,
                gold_22k =rates.gold_22k,
                silver   =rates.silver,
            ))
            logger.info("Inserted new metal_rates row for %s", rates.rate_date)
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to persist metal rates to DB: %s", exc)
        return False
    finally:
        db.close()
