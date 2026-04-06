

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from collections.abc import AsyncIterator

import httpx

from sentinel_osint.models.raw import RawRecord

from .base import BaseCollector

logger = logging.getLogger(__name__)

# Platforms to check for username presence.
# (platform_name, profile_url_template with {username}, expected_status_if_exists)
PLATFORMS: list[tuple[str, str, int]] = [
    ("github", "https://api.github.com/users/{username}", 200),
    ("twitter", "https://twitter.com/{username}", 200),
    ("instagram", "https://www.instagram.com/{username}/", 200),
    ("reddit", "https://www.reddit.com/user/{username}/about.json", 200),
    ("linkedin", "https://www.linkedin.com/in/{username}", 200),
]


class UsernameCollector(BaseCollector):
    """
    Cross-platform username search. Unlike geo-based collectors, this takes
    a username from an existing RawRecord and checks for the same handle
    across platforms. The collect() lat/lon are used to tag results with a
    reference location but the search itself is username-based.
    """

    name = "username"
    rate_limit_per_minute = 5

    async def collect(self, lat: float, lon: float, radius_m: float) -> AsyncIterator[RawRecord]:
        # This collector is triggered indirectly via search_username()
        return
        yield  # type: ignore[misc]

    async def search_username(
        self, username: str, ref_lat: float = 0.0, ref_lon: float = 0.0
    ) -> AsyncIterator[RawRecord]:
        """Check if a username exists across multiple platforms."""
        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "SENTINEL-OSINT/0.1"},
        ) as client:
            for platform, url_template, expected_status in PLATFORMS:
                await self._rate_limit()
                # Randomised delay to avoid pattern detection
                await asyncio.sleep(random.uniform(0.5, 2.0))

                url = url_template.format(username=username)
                try:
                    resp = await client.get(url)
                    if resp.status_code == 429:
                        logger.warning("[username:%s] 429 on %s", platform, url)
                        continue
                    if resp.status_code == expected_status:
                        yield RawRecord(
                            id=str(uuid.uuid4()),
                            source=f"username_{platform}",
                            source_id=username,
                            lat=ref_lat,
                            lon=ref_lon,
                            raw_data={
                                "platform": platform,
                                "username": username,
                                "url": url,
                                "status": resp.status_code,
                            },
                        )
                except httpx.HTTPError as exc:
                    logger.warning("[username:%s] %s", platform, exc)
