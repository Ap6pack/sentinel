

from __future__ import annotations

from fastapi import APIRouter

from sentinel_osint.collectors import ALL_COLLECTORS

health_router = APIRouter()


@health_router.get("/api/v1/health")
async def health() -> dict:
    collector_status = {}
    for cls in ALL_COLLECTORS:
        c = cls()
        collector_status[c.name] = {
            "available": await c.is_available(),
            "requires_api_key": c.requires_api_key,
        }
    return {
        "module": "sentinel-osint",
        "status": "ok",
        "collectors": collector_status,
    }
