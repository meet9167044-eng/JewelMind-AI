"""
backend/app/models/user.py — SQLAlchemy User Model
====================================================
Represents Table 1 (users) from DATABASE_SCHEMA.md.

Columns:
    user_id       INT AUTO_INCREMENT PRIMARY KEY
    email         VARCHAR(255) UNIQUE NOT NULL
    password_hash VARCHAR(512) NOT NULL
    full_name     VARCHAR(255) NOT NULL
    created_at    DATETIME (auto-set on insert)
    updated_at    DATETIME (auto-updated on every change)

Rules:
    - Passwords are NEVER stored in plaintext.
    - Only bcrypt hashes are stored in password_hash.
    - JWT tokens contain only user_id — no other PII.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<User id={self.user_id} email={self.email!r}>"
