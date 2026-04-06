

from __future__ import annotations

import redis.asyncio as redis

from .envelope import EventEnvelope

STREAM_NAME = "sentinel:events"
MAX_LEN = 50_000


class BusPublisher:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self._client = redis.from_url(redis_url, decode_responses=True)

    async def publish(self, envelope: EventEnvelope) -> str:
        """Returns the Redis stream entry ID."""
        msg_id = await self._client.xadd(
            STREAM_NAME,
            envelope.to_redis(),
            maxlen=MAX_LEN,
            approximate=True,
        )
        return msg_id

    async def close(self) -> None:
        await self._client.aclose()


class BusConsumer:
    def __init__(
        self,
        group: str,
        consumer: str,
        kinds: list[str] | None = None,
        redis_url: str = "redis://localhost:6379",
    ):
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._group = group
        self._consumer = consumer
        self._kinds = set(kinds) if kinds else None
        self._stream = STREAM_NAME

    async def ensure_group(self) -> None:
        try:
            await self._client.xgroup_create(
                self._stream, self._group, id="0", mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def __aiter__(self):
        await self.ensure_group()
        while True:
            results = await self._client.xreadgroup(
                self._group,
                self._consumer,
                {self._stream: ">"},
                count=100,
                block=1000,
            )
            for _, messages in results or []:
                for msg_id, fields in messages:
                    envelope = EventEnvelope.from_redis(fields)
                    if self._kinds is None or envelope.kind in self._kinds:
                        yield envelope
                    await self._client.xack(self._stream, self._group, msg_id)

    async def close(self) -> None:
        await self._client.aclose()
