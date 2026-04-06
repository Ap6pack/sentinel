

from __future__ import annotations

from fastapi import APIRouter

from sentinel_ai.config import ai_settings

health_router = APIRouter()


@health_router.get("/api/v1/health")
async def health() -> dict:
    return {
        "module": "sentinel-ai",
        "status": "ok",
        "max_calls_per_hour": ai_settings.max_calls_per_hour,
        "osint_api_url": ai_settings.osint_api_url,
    }
