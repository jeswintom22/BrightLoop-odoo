import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SQLITE_PATH = os.path.join(BACKEND_DIR, "brightloop.db").replace("\\", "/")


class Settings(BaseSettings):
    PROJECT_NAME: str = "BrightLoop API - Product, Plans & Pricing"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "FastAPI backend for BrightLoop subscription, pricing, and tax management."
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Database Configuration (Supabase PostgreSQL / Local fallback)
    DATABASE_URL: str = f"sqlite:///{DEFAULT_SQLITE_PATH}"

    # Frontend and CORS Origins
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://brightloop-odoo.vercel.app",
    ]

    # Connection pool configuration for Render Free Web Service & Supabase
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 300  # Recycle connections every 5 minutes
    DB_POOL_PRE_PING: bool = True  # Detect dead connections before reusing

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]], values) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            origins = [i.strip() for i in v.split(",") if i.strip()]
            return origins
        elif isinstance(v, list):
            return v
        return ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
