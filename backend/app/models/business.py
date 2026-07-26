"""
backend/app/models/business.py — SQLAlchemy Business Model
===========================================================
Represents Table 2 (businesses) from DATABASE_SCHEMA.md.

This is the multi-tenancy anchor. Every business-data table
(products, purchases, sales) references business_id from here.

Columns:
    business_id    INT AUTO_INCREMENT PRIMARY KEY
    owner_user_id  INT NOT NULL  FK → users(user_id) ON DELETE CASCADE
    business_name  VARCHAR(255)  NOT NULL
    owner_name     VARCHAR(255)
    email          VARCHAR(255)
    phone          VARCHAR(50)
    created_at     DATETIME  (auto-set on insert)
    updated_at     DATETIME  (auto-updated on change)

Security rule:
    Every query that reads business data MUST filter by business_id.
    A query that crosses business boundaries without an explicit filter
    is a critical data-isolation bug (PROJECT_RULES.md, Rule 11).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Business(Base):
    __tablename__ = "businesses"

    business_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    owner_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationship back to the owner (optional — used for joins)
    owner = relationship("User", backref="businesses", lazy="select")

    def __repr__(self) -> str:
        return f"<Business id={self.business_id} name={self.business_name!r}>"
