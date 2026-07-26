"""
backend/app/models/purchase.py — SQLAlchemy Purchase Model
===========================================================
Represents Table 4 (purchases) from DATABASE_SCHEMA.md.

Columns:
    purchase_id   INT AUTO_INCREMENT PRIMARY KEY
    business_id   INT NOT NULL  FK → businesses(business_id) ON DELETE CASCADE
    product_id    INT NOT NULL  FK → products(product_id) ON DELETE CASCADE
    purchase_date DATETIME NOT NULL
    quantity      INT NOT NULL
    weight        DECIMAL(10,4) NOT NULL
    metal_rate    DECIMAL(12,2) NOT NULL  (rate per gram at acquisition time)
    metal_cost    DECIMAL(12,2) NOT NULL
    making_cost   DECIMAL(12,2) NOT NULL  (labor paid to supplier/karigar)
    total_cost    DECIMAL(12,2) NOT NULL  (= metal_cost + making_cost)

Analytics rule:
    COGS for a serialised item = purchases.total_cost (exact cost from this table).
    This value is denormalised into sales.cost_basis at billing time.
"""

from datetime import datetime

from sqlalchemy import DECIMAL, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class Purchase(Base):
    __tablename__ = "purchases"

    purchase_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    business_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("businesses.business_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purchase_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False)
    metal_rate: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    metal_cost: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    making_cost: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    total_cost: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<Purchase id={self.purchase_id} "
            f"product={self.product_id} business={self.business_id}>"
        )
