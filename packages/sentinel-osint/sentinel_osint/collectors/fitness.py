

from __future__ import annotations

import logging
import uuid
from collections import Counter
from collections.abc import AsyncIterator

import httpx
import numpy as np
from sklearn.cluster import DBSCAN

from sentinel_osint.config import osint_settings
from sentinel_osint.models.raw import RawRecord

from .base import BaseCollector

logger = logging.getLogger(__name__)


class FitnessCollector(BaseCollector):
    name = "strava"
    rate_limit_per_minute = 15
    requires_api_key = True

    def __init__(self) -> None:
        super().__init__()
        self._token = osint_settings.strava_token

    async def is_available(self) -> bool:
        return bool(self._token)

    async def collect(self, lat: float, lon: float, radius_m: float) -> AsyncIterator[RawRecord]:
        if not self._token:
            return

        delta = radius_m / 111_000
        bounds = f"{lat - delta},{lon - delta},{lat + delta},{lon + delta}"
        url = "https://www.strava.com/api/v3/segments/explore"
        params = {"bounds": bounds, "activity_type": "running"}

        await self._rate_limit()
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "60"))
                    logger.warning("[strava] 429 on %s, retry-after %ds", url, retry_after)
                    return
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("[strava] %s", exc)
                return

            for seg in resp.json().get("segments", []):
                start = seg.get("start_latlng")
                if not start or len(start) < 2:
                    continue
                yield RawRecord(
                    id=str(uuid.uuid4()),
                    source="strava",
                    source_id=str(seg["id"]),
                    lat=start[0],
                    lon=start[1],
                    raw_data=seg,
                )


def infer_home_coord(
    route_starts: list[tuple[float, float]],
) -> tuple[float, float] | None:
    """
    Given a list of (lat, lon) route start points, find the most common
    origin cluster — likely home address.
    Returns None if fewer than 3 routes or no dominant cluster.
    """
    if len(route_starts) < 3:
        return None
    coords = np.array(route_starts)
    db = DBSCAN(eps=0.0013, min_samples=2, algorithm="ball_tree", metric="haversine")
    labels = db.fit_predict(np.radians(coords))
    valid = [label for label in labels if label != -1]
    if not valid:
        return None
    most_common = Counter(valid).most_common(1)[0][0]
    cluster_pts = coords[labels == most_common]
    return float(cluster_pts[:, 0].mean()), float(cluster_pts[:, 1].mean())
