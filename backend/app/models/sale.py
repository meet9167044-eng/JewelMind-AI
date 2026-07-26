"""
backend/app/models/sale.py — SQLAlchemy Sale Model
====================================================
Represents Table 5 (sales) from DATABASE_SCHEMA.md.

Columns:
    sale_id        INT AUTO_INCREMENT PRIMARY KEY
    business_id    INT NOT NULL  FK → businesses(business_id) ON DELETE CASCADE
    product_id     INT NOT NULL  FK → products(product_id) ON DELETE CASCADE
    sale_date      DATETIME NOT NULL
    quantity       INT NOT NULL
    weight         DECIMAL(10,4) NOT NULL
    selling_price  DECIMAL(12,2) NOT NULL  (gross price before discount)
    making_charge  DECIMAL(12,2) NOT NULL  (labor billed to customer)
    discount       DECIMAL(12,2) NOT NULL DEFAULT 0.00
    cost_basis     DECIMAL(12,2) NOT NULL  (denormalised from purchases.total_cost)

Analytics formulas (ANALYTICS_FORMULAS.md Section 1):
    Net Revenue  = selling_price - discount
    COGS         = cost_basis
    Gross Profit = selling_price - discount - cost_basis
"""

from datetime import datetime

from sqlalchemy import DECIMAL, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class Sale(Base):
    __tablename__ = "sales"

    sale_id: Mapped[int] = mapped_column(
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
    sale_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False)
    selling_price: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    making_charge: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    discount: Mapped[float] = mapped_column(
        DECIMAL(12, 2), nullable=False, server_default="0.00"
    )
    cost_basis: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<Sale id={self.sale_id} "
            f"product={self.product_id} business={self.business_id}>"
        )
