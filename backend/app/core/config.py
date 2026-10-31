from functools import lru_cache
from typing import Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    project_name: str = "BrightLoop Subscription Management API"
    api_v1_str: str = "/api/v1"
    environment: str = "development"

    # Supabase Postgres (pooled) in prod; SQLite fallback for local dev/tests.
    database_url: str = "sqlite:///./brightloop.db"

    # Comma-separated in .env; normalized to a list by the validator below.
    cors_origins: Union[str, list[str]] = ["http://localhost:5173"]

    # Auth — contract owned by Person 1. This app only needs to resolve the
    # caller's identity + roles from a Bearer token.
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    auth_dev_bypass: bool = True  # dev only: skip JWT, act as a finance admin

    # Shared secret for POST /api/v1/internal/billing/run (GitHub Actions).
    internal_job_token: str = "dev-internal-token"

    # Email (Resend). Empty key disables sending.
    resend_api_key: str = ""
    resend_from: str = "Brightloop Billing <billing@brightloop.example>"

    default_currency: str = "INR"

    # Until P2/P3 modules land, billing uses in-process stub providers.
    use_stub_providers: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, list[str]]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        if isinstance(v, list):
            return v
        return ["*"]


settings = Settings()


@lru_cache
def get_settings() -> Settings:
    return settings
