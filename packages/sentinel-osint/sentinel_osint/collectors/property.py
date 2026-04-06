

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

import httpx

from sentinel_osint.models.raw import RawRecord

from .base import BaseCollector

logger = logging.getLogger(__name__)

# Open data portals that serve GeoJSON for property/parcel data.
# Each entry: (name, URL template with {bbox} placeholder for minlon,minlat,maxlon,maxlat)
OPEN_DATA_ENDPOINTS: list[tuple[str, str]] = [
    (
        "openaddresses",
        "https://batch.openaddresses.io/api/data?bbox={bbox}&limit=100",
    ),
]


class PropertyCollector(BaseCollector):
    name = "property"
    rate_limit_per_minute = 60

    async def collect(self, lat: float, lon: float, radius_m: float) -> AsyncIterator[RawRecord]:
        delta = radius_m / 111_000
        bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"

        async with httpx.AsyncClient(timeout=15) as client:
            for source_name, url_template in OPEN_DATA_ENDPOINTS:
                url = url_template.format(bbox=bbox)
                await self._rate_limit()
                try:
                    resp = await client.get(url)
                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("Retry-After", "60"))
                        logger.warning(
                            "[property:%s] 429, retry-after %ds", source_name, retry_after
                        )
                        continue
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("[property:%s] %s", source_name, exc)
                    continue

                data = resp.json()
                features = data if isinstance(data, list) else data.get("features", [])
                for feature in features:
                    props = feature.get("properties", feature) if isinstance(feature, dict) else {}
                    geom = feature.get("geometry", {}) if isinstance(feature, dict) else {}
                    coords = geom.get("coordinates", [])
                    feat_lon = coords[0] if len(coords) >= 2 else None
                    feat_lat = coords[1] if len(coords) >= 2 else None
                    yield RawRecord(
                        id=str(uuid.uuid4()),
                        source="property",
                        source_id=props.get("id", str(uuid.uuid4())),
                        lat=feat_lat,
                        lon=feat_lon,
                        raw_data=props,
                    )
