

from __future__ import annotations

from datetime import datetime, timezone

import httpx

MODULE_HEALTH_URLS: dict[str, str] = {
    "rf": "http://localhost:5050/api/v1/health",
    "osint": "http://localhost:5001/api/v1/health",
    "ai": "http://localhost:5002/api/v1/health",
}


async def aggregate_health() -> dict:
    """Poll all module health endpoints and return a unified status."""
    results: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=3.0) as c:
        for name, url in MODULE_HEALTH_URLS.items():
            try:
                r = await c.get(url)
                results[name] = r.json()
            except Exception as e:
                results[name] = {"status": "unreachable", "error": str(e)}
    overall = (
        "ok"
        if all(v.get("status") == "ok" for v in results.values())
        else "degraded"
    )
    return {
        "module": "sentinel-core",
        "ts": datetime.now(timezone.utc).isoformat(),
        "modules": results,
        "overall": overall,
    }
