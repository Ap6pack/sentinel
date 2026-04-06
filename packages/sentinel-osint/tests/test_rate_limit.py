

import time

from sentinel_osint.collectors.base import BaseCollector


class FakeCollector(BaseCollector):
    name = "fake"
    rate_limit_per_minute = 3

    async def collect(self, lat, lon, radius_m):
        yield  # type: ignore[misc]


async def test_rate_limit_allows_within_limit():
    c = FakeCollector()
    for _ in range(3):
        await c._rate_limit()
    # Should not block — 3 calls within limit of 3/min
    assert len(c._call_times) == 3


async def test_rate_limit_sliding_window_cleanup():
    c = FakeCollector()
    # Simulate old call times (>60s ago)
    c._call_times = [time.monotonic() - 120, time.monotonic() - 90]
    await c._rate_limit()
    # Old entries should be cleaned up, only new one remains
    assert len(c._call_times) == 1
