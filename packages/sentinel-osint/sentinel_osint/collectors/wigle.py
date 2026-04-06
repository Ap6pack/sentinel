

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

import httpx

from sentinel_osint.config import osint_settings
from sentinel_osint.models.raw import RawRecord

from .base import BaseCollector

logger = logging.getLogger(__name__)

WIGLE_SEARCH_URL = "https://api.wigle.net/api/v2/network/search"


class WiGLECollector(BaseCollector):
    """Collects WiFi network data from WiGLE.net for a given area."""

    name = "wigle"
    rate_limit_per_minute = 10
    requires_api_key = True

    def __init__(self) -> None:
        super().__init__()
        self._api_key = osint_settings.wigle_api_key

    async def is_available(self) -> bool:
        return bool(self._api_key)

    async def collect(self, lat: float, lon: float, radius_m: float) -> AsyncIterator[RawRecord]:
        if not self._api_key:
            return
        latrange = radius_m / 111_000  # rough degrees per metre
        params = {
            "latrange1": lat - latrange,
            "latrange2": lat + latrange,
            "longrange1": lon - latrange,
            "longrange2": lon + latrange,
            "freenet": "false",
            "paynet": "false",
        }
        await self._rate_limit()
        async with httpx.AsyncClient(timeout=15) as c:
            try:
                r = await c.get(
                    WIGLE_SEARCH_URL,
                    params=params,
                    headers={"Authorization": f"Basic {self._api_key}"},
                )
                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", "60"))
                    logger.warning("[wigle] 429 rate limited, Retry-After=%d", retry_after)
                    return
                r.raise_for_status()
                for net in r.json().get("results", []):
                    yield RawRecord(
                        id=str(uuid.uuid4()),
                        source="wigle",
                        source_id=net.get("netid", ""),
                        lat=net.get("trilat"),
                        lon=net.get("trilong"),
                        raw_data=net,
                    )
            except httpx.HTTPStatusError as e:
                logger.warning("[wigle] HTTP %d: %s", e.response.status_code, e)
            except httpx.TimeoutException:
                logger.warning("[wigle] request timeout")
            except Exception as e:
                logger.warning("[wigle] %s", e)
