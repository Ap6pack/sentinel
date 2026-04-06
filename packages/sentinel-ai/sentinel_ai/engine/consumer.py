

from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as redis

from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

from sentinel_ai.config import ai_settings
from sentinel_ai.engine.window import EventWindow

logger = logging.getLogger(__name__)

STREAM = "sentinel:events"

# Event kinds the AI engine cares about
RELEVANT_KINDS = {
    EventKind.AIRCRAFT,
    EventKind.VESSEL,
    EventKind.WIFI,
    EventKind.BLUETOOTH,
    EventKind.PROFILE,
    EventKind.PROFILE_LINK,
}


class AiConsumer:
    """Reads events from Redis Streams and feeds them into the EventWindow."""

    def __init__(self, window: EventWindow, redis_url: str | None = None) -> None:
        self._window = window
        self._redis_url = redis_url or ai_settings.redis_url
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _consume_loop(self) -> None:
        client = redis.from_url(self._redis_url, decode_responses=True)
        last_id = "$"
        while True:
            try:
                results = await client.xread(
                    {STREAM: last_id}, count=100, block=500
                )
                for _, messages in results or []:
                    for msg_id, fields in messages:
                        last_id = msg_id
                        try:
                            envelope = EventEnvelope.model_validate_json(
                                fields["data"]
                            )
                        except Exception:
                            continue
                        if envelope.kind in RELEVANT_KINDS:
                            await self._window.push(envelope)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("[consumer] Redis error: %s", e)
                await asyncio.sleep(2)
        await client.aclose()
