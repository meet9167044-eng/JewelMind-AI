"""
config.py — Application Settings
=================================
All environment variables are read once here via pydantic-settings.

Required .env (or system env) variables:
    MYSQL_HOST
    MYSQL_PORT          (default: 3306)
    MYSQL_DATABASE
    MYSQL_USER
    MYSQL_PASSWORD

    JWT_SECRET_KEY

    METAL_RATE_API_PROVIDER
    METAL_RATE_API_URL
    METAL_RATE_API_KEY
    METAL_RATE_REFRESH_INTERVAL   (seconds, default: 86400)

    LLM_API_KEY

Do NOT import database sessions or models here — this module has
zero dependencies on the rest of the application.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reads configuration from environment variables (or a .env file)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "jewelmind_db"
    mysql_user: str = "root"
    mysql_password: str = ""

    # ── Authentication ────────────────────────────────────────────────────────
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_days: int = 30

    # ── Metal Rate Fetch Service ──────────────────────────────────────────────
    metal_rate_api_provider: str = "GoldAPI"
    metal_rate_api_url: str = ""
    metal_rate_api_key: str = ""
    metal_rate_refresh_interval: int = 86400   # seconds (default: once per day)

    # ── AI Copilot ────────────────────────────────────────────────────────────
    llm_api_key: str = ""

    # ── Derived property ─────────────────────────────────────────────────────
    @property
    def database_url(self) -> str:
        """
        SQLAlchemy connection URL for MySQL via PyMySQL.
        Format: mysql+pymysql://user:password@host:port/database
        """
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )


# Single shared instance imported by the rest of the application.
settings = Settings()
