import os
from functools import lru_cache
from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SQLITE_PATH = os.path.join(BACKEND_DIR, "brightloop.db").replace("\\", "/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    PROJECT_NAME: str = "BrightLoop Subscription Management API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = (
        "FastAPI backend for BrightLoop: catalog, subscriptions, billing and payments."
    )
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Database Configuration (Supabase PostgreSQL / Local fallback)
    DATABASE_URL: str = f"sqlite:///{DEFAULT_SQLITE_PATH}"

    # Frontend and CORS Origins
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://brightloop-odoo.vercel.app",
    ]

    # Connection pool configuration for Render Free Web Service & Supabase
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 300  # Recycle connections every 5 minutes
    DB_POOL_PRE_PING: bool = True  # Detect dead connections before reusing

    # Auth — contract owned by Person 1. This app only needs to resolve the
    # caller's identity + roles from a Bearer token.
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    AUTH_DEV_BYPASS: bool = True  # dev only: skip JWT, act as a finance admin

    # Shared secret for POST /api/v1/internal/billing/run (GitHub Actions).
    INTERNAL_JOB_TOKEN: str = "dev-internal-token"

    # Email (Resend). Empty key disables sending.
    RESEND_API_KEY: str = ""
    RESEND_FROM: str = "Brightloop Billing <billing@brightloop.example>"
    RESEND_WEBHOOK_SECRET: str = ""
    NOTIFICATION_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=20)
    NOTIFICATION_RETRY_DELAY_MINUTES: int = Field(default=15, ge=1, le=1440)
    PAYMENT_INSTRUCTIONS: str = "Please use the secure payment options in your account."

    DEFAULT_CURRENCY: str = "INR"

    # ── Phase 2 (P4): AI Finance Copilot provider ───────────────────────────
    # "none" (default, deterministic template engine — no external calls),
    # "openai" or "gemini". Missing AI_API_KEY degrades to the template path.
    AI_PROVIDER: str = "none"
    AI_API_KEY: str = ""
    AI_MODEL: str = "gpt-4o-mini"          # gemini e.g. "gemini-1.5-flash"
    AI_TIMEOUT_S: float = 20.0
    AI_MAX_TOKENS: int = 800
    AI_RATE_LIMIT_PER_MINUTE: int = 20     # per user, per process

    # Until P2/P3 modules land, billing uses in-process stub providers.
    USE_STUB_PROVIDERS: bool = False

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        if isinstance(v, list):
            return v
        return ["*"]


settings = Settings()


@lru_cache
def get_settings() -> Settings:
    return settings
