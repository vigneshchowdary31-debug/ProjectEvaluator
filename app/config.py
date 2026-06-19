"""
Application configuration loaded from environment variables.
"""

from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── JWT ──────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./audit_platform.db"

    # ── Admin seed ───────────────────────────────────────────────────
    ADMIN_EMAIL: str = "admin@audit.com"
    ADMIN_PASSWORD: str = "admin123"

    # ── App ──────────────────────────────────────────────────────────
    APP_NAME: str = "AI Project Audit Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Gemini AI ─────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # ── GitHub ────────────────────────────────────────────────────────
    GITHUB_TOKEN: str = ""
    GITHUB_CACHE_TTL_HOURS: int = 24

    # ── Google Drive ──────────────────────────────────────────────────
    GOOGLE_CREDENTIALS_JSON: str = ""
    GOOGLE_DRIVE_FOLDER_ID: str = ""



    # ── CORS ─────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["*"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
