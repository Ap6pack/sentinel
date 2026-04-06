

from __future__ import annotations

import logging

import redis

from sentinel_common.envelope import EventEnvelope

logger = logging.getLogger(__name__)


class SyncRFPublisher:
    """Publishes decoder events to Redis Streams using a sync client.

    sentinel-rf runs under gevent (Flask-SocketIO), so the async BusPublisher
    cannot be used. This sync publisher is thread-safe and called from the
    decoder background thread. See ADR-002.
    """

    def __init__(self, redis_url: str):
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._stream = "sentinel:events"
        self._maxlen = 50_000
        self._gps_lat: float | None = None
        self._gps_lon: float | None = None

    def publish(self, envelope: EventEnvelope) -> None:
        """Enrich with cached GPS if event lacks coords, then publish."""
        if envelope.lat is None and self._gps_lat is not None:
            envelope = envelope.model_copy(
                update={"lat": self._gps_lat, "lon": self._gps_lon}
            )
        self._client.xadd(
            self._stream,
            {"data": envelope.model_dump_json()},
            maxlen=self._maxlen,
            approximate=True,
        )
