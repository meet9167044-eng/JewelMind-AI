"""
backend/app/models/metal_rate.py — SQLAlchemy MetalRate Model
==============================================================
Represents Table 6 (metal_rates) from DATABASE_SCHEMA.md.

This is a GLOBAL reference table — no business_id column.
All businesses on the platform share the same commodity rate data.

Primary Key: rate_date (DATE) — one row per calendar day.

Population rules:
    - PRODUCTION: Populated automatically by the Metal Rate Fetch Service
      (background scheduler, external API). Analytics reads from here.
    - DEVELOPMENT: Historical metal_rates.csv is used ONLY as a dev fixture
      for local testing and seeding demo historical charts. It is NEVER
      used or uploaded in production.

Columns:
    rate_date  DATE PRIMARY KEY
    gold_24k   DECIMAL(12,2) NOT NULL  (per gram, INR)
    gold_22k   DECIMAL(12,2) NOT NULL  (per gram, INR)
    silver     DECIMAL(12,2) NOT NULL  (per gram, INR)
"""

from datetime import date

from sqlalchemy import DECIMAL, Date
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class MetalRate(Base):
    __tablename__ = "metal_rates"

    rate_date: Mapped[date] = mapped_column(Date, primary_key=True)
    gold_24k: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    gold_22k: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    silver: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<MetalRate date={self.rate_date} "
            f"gold_24k={self.gold_24k} gold_22k={self.gold_22k} silver={self.silver}>"
        )
