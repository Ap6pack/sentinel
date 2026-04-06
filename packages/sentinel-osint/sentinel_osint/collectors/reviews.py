

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

import httpx

from sentinel_osint.config import osint_settings
from sentinel_osint.models.raw import RawRecord

from .base import BaseCollector

logger = logging.getLogger(__name__)


class ReviewsCollector(BaseCollector):
    name = "google_reviews"
    rate_limit_per_minute = 20
    requires_api_key = True

    def __init__(self) -> None:
        super().__init__()
        self._api_key = osint_settings.google_places_api_key

    async def is_available(self) -> bool:
        return bool(self._api_key)

    async def collect(self, lat: float, lon: float, radius_m: float) -> AsyncIterator[RawRecord]:
        if not self._api_key:
            return

        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{lat},{lon}",
            "radius": min(radius_m, 50000),
            "key": self._api_key,
        }

        await self._rate_limit()
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 429:
                    logger.warning("[google_reviews] 429 on nearbysearch")
                    return
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("[google_reviews] %s", exc)
                return

            for place in resp.json().get("results", []):
                place_id = place.get("place_id", "")
                place_lat = place.get("geometry", {}).get("location", {}).get("lat")
                place_lon = place.get("geometry", {}).get("location", {}).get("lng")

                # Fetch reviews for this place
                await self._rate_limit()
                try:
                    detail_resp = await client.get(
                        "https://maps.googleapis.com/maps/api/place/details/json",
                        params={
                            "place_id": place_id,
                            "fields": "reviews",
                            "key": self._api_key,
                        },
                    )
                    if detail_resp.status_code == 429:
                        logger.warning("[google_reviews] 429 on details")
                        return
                    detail_resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("[google_reviews] details %s", exc)
                    continue

                reviews = detail_resp.json().get("result", {}).get("reviews", [])
                for review in reviews:
                    author_url = review.get("author_url", "")
                    yield RawRecord(
                        id=str(uuid.uuid4()),
                        source="google_reviews",
                        source_id=author_url or str(uuid.uuid4()),
                        lat=place_lat,
                        lon=place_lon,
                        raw_data={
                            "author_name": review.get("author_name", ""),
                            "author_url": author_url,
                            "rating": review.get("rating"),
                            "text": review.get("text", ""),
                            "place_id": place_id,
                            "place_name": place.get("name", ""),
                        },
                    )
