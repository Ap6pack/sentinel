

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from sentinel_osint.models.raw import RawRecord

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """
    Abstract collector with built-in sliding-window rate limiter.
    Subclasses must implement collect() and set class-level attributes.
    """

    name: str = "base"
    rate_limit_per_minute: int = 30
    requires_api_key: bool = False

    def __init__(self) -> None:
        self._call_times: list[float] = []

    async def _rate_limit(self) -> None:
        """Sliding window rate limiter. Call before every outbound HTTP request."""
        now = time.monotonic()
        self._call_times = [t for t in self._call_times if now - t < 60]
        if len(self._call_times) >= self.rate_limit_per_minute:
            sleep_for = 60 - (now - self._call_times[0]) + 0.1
            logger.debug("[%s] rate limit: sleeping %.1fs", self.name, sleep_for)
            await asyncio.sleep(sleep_for)
        self._call_times.append(time.monotonic())

    @abstractmethod
    async def collect(self, lat: float, lon: float, radius_m: float) -> AsyncIterator[RawRecord]:
        """
        Yield RawRecord objects for the given area.
        Must call self._rate_limit() before each outbound HTTP request.
        Must never raise on HTTP errors — log and yield nothing.
        """
        yield  # type: ignore[misc]

    async def is_available(self) -> bool:
        """Return False if API key missing or service unreachable."""
        return True
