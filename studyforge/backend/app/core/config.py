"""
Centralized application configuration.

All secrets and environment-dependent values are read from environment
variables (see .env.example). Nothing here is hard-coded.
"""
from __future__ import annotations

import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- App ---
    APP_NAME: str = "StudyForge"
    ENV: str = os.getenv("ENV", "development")

    # --- Security ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    JWT_ALGORITHM: str = "HS256"

    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/processed/studyforge.db")

    # --- Storage ---
    RAW_DATA_DIR: str = os.getenv("RAW_DATA_DIR", "./data/raw")
    VECTOR_STORE_DIR: str = os.getenv("VECTOR_STORE_DIR", "./data/processed/vector_store")

    # --- LLM ---
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_BASE_URL: str = os.getenv(
    "ANTHROPIC_BASE_URL",
    "https://api.anthropic.com",
    )
    LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))

    # --- RAG ---
    CHUNK_SIZE_CHARS: int = int(os.getenv("CHUNK_SIZE_CHARS", "800"))
    CHUNK_OVERLAP_CHARS: int = int(os.getenv("CHUNK_OVERLAP_CHARS", "150"))
    TOP_K_RETRIEVAL: int = int(os.getenv("TOP_K_RETRIEVAL", "4"))
    DEFAULT_TOPIC_COUNT: int = int(os.getenv("DEFAULT_TOPIC_COUNT", "5"))

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    def validate(self) -> None:
        if not self.SECRET_KEY:
            # Fail loudly rather than silently using an insecure default in production.
            if self.ENV == "production":
                raise RuntimeError("SECRET_KEY must be set in production environments.")
            self.SECRET_KEY = "dev-only-insecure-secret-change-me"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate()
    return settings
