"""
backend/app/models/product.py — SQLAlchemy Product Model
=========================================================
Represents Table 3 (products) from DATABASE_SCHEMA.md.

Every product belongs to exactly one business (business_id FK).
Analytics queries MUST always filter by business_id.

Columns:
    product_id    INT AUTO_INCREMENT PRIMARY KEY
    business_id   INT NOT NULL  FK → businesses(business_id) ON DELETE CASCADE
    sku           VARCHAR(100)  NOT NULL  (unique per business, not globally)
    product_name  VARCHAR(255)  NOT NULL
    category      VARCHAR(100)  NOT NULL  (chain, necklace, payal, coin, utensil, ring, bangle, earring)
    metal         VARCHAR(50)   NOT NULL  (gold, silver)
    purity        VARCHAR(50)   NOT NULL  (22K, 24K, 18K, 925, ...)
    gross_weight  DECIMAL(10,4) NOT NULL
    net_weight    DECIMAL(10,4) NOT NULL

Constraints:
    UNIQUE (business_id, sku) — same SKU may exist in different businesses
"""

from sqlalchemy import (
    DECIMAL,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        # SKU uniqueness is per-business, not global
        UniqueConstraint("business_id", "sku", name="uq_products_business_sku"),
    )

    product_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    business_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("businesses.business_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    metal: Mapped[str] = mapped_column(String(50), nullable=False)
    purity: Mapped[str] = mapped_column(String(50), nullable=False)
    gross_weight: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False)
    net_weight: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False)

    def __repr__(self) -> str:
        return f"<Product id={self.product_id} sku={self.sku!r} business={self.business_id}>"
