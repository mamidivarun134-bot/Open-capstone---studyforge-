from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.llm import LLMClient

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    llm_client = LLMClient()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.ENV,
        "llm_configured": llm_client.is_configured,
    }
