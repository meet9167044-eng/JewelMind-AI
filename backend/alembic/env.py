"""
backend/alembic/env.py — Alembic Migration Environment
=========================================================
Configures the migration context so that:
    1. The MySQL URL comes from backend/app/config.py (not hardcoded in alembic.ini).
    2. ORM models' metadata is registered here so autogenerate works (Phase 7).

Usage:
    # Generate a migration:
    alembic revision --autogenerate -m "add users table"

    # Apply migrations:
    alembic upgrade head

    # Downgrade one step:
    alembic downgrade -1
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Alembic config object (reads alembic.ini) ─────────────────────────────────
config = context.config

# ── Set up Python logging from alembic.ini ────────────────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import application settings and metadata ──────────────────────────────────
from backend.app.config import settings
from backend.app.database import Base  # noqa: F401

# Import models here so autogenerate can detect schema changes.
# Add each new model module as it is created in subsequent phases.
from backend.app.models import user as _user_model  # noqa: F401
from backend.app.models import business as _business_model  # noqa: F401
from backend.app.models import product as _product_model  # noqa: F401
from backend.app.models import purchase as _purchase_model  # noqa: F401
from backend.app.models import sale as _sale_model  # noqa: F401
from backend.app.models import metal_rate as _metal_rate_model  # noqa: F401

# Provide the metadata for autogenerate
target_metadata = Base.metadata


# ── Override sqlalchemy.url from environment ──────────────────────────────────
config.set_main_option("sqlalchemy.url", settings.database_url)


# ── Offline migrations (generates SQL scripts without a live DB) ──────────────
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL statements to stdout — useful for reviewing before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (applies directly to the live DB) ──────────────────────
def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    Creates a real engine connection and applies migrations immediately.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
