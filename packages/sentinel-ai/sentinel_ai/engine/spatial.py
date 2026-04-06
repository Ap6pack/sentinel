

from __future__ import annotations

import logging

import httpx

from sentinel_common.envelope import EventEnvelope

from sentinel_ai.config import ai_settings

logger = logging.getLogger(__name__)


async def find_nearby_profiles(
    envelope: EventEnvelope,
    osint_url: str | None = None,
) -> list[dict]:
    """
    Query sentinel-osint for profiles near the event's coordinates.
    Returns empty list if event has no coordinates or OSINT is unreachable.
    """
    if envelope.lat is None or envelope.lon is None:
        return []
    base_url = osint_url or ai_settings.osint_api_url
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                f"{base_url}/api/v1/profiles",
                params={
                    "lat": envelope.lat,
                    "lon": envelope.lon,
                    "radius_m": ai_settings.spatial_radius_m,
                },
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.warning("[spatial] %s", e)
        return []


async def find_profiles_for_batch(
    events: list[EventEnvelope],
    osint_url: str | None = None,
) -> list[dict]:
    """Collect unique nearby profiles for a batch of events."""
    seen: set[str] = set()
    profiles: list[dict] = []
    for event in events:
        for p in await find_nearby_profiles(event, osint_url=osint_url):
            eid = p.get("entity_id", "")
            if eid not in seen:
                seen.add(eid)
                profiles.append(p)
    return profiles
