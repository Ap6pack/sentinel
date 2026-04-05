# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from __future__ import annotations

import logging

from sentinel_common.bus import BusPublisher
from sentinel_common.envelope import EventEnvelope

logger = logging.getLogger(__name__)


class RFPublisher:
    """Publishes decoder events to the Redis Streams bus with optional GPS enrichment."""

    def __init__(self, bus: BusPublisher):
        self._bus = bus
        self._gps_lat: float | None = None
        self._gps_lon: float | None = None

    async def publish(self, envelope: EventEnvelope) -> None:
        """Enrich with cached GPS if event lacks coords, then publish."""
        if envelope.lat is None and self._gps_lat is not None:
            envelope = envelope.model_copy(
                update={"lat": self._gps_lat, "lon": self._gps_lon}
            )
        await self._bus.publish(envelope)
