

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sentinel_common.envelope import EventEnvelope

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 30
MIN_EVENTS_TO_CORRELATE = 2


class EventWindow:
    """Batches incoming events into time windows before correlation."""

    def __init__(
        self,
        on_window_ready: Callable[[list[EventEnvelope]], Awaitable[None]],
        window_seconds: int = WINDOW_SECONDS,
        min_events: int = MIN_EVENTS_TO_CORRELATE,
    ) -> None:
        self._buffer: list[EventEnvelope] = []
        self._on_ready = on_window_ready
        self._window_seconds = window_seconds
        self._min_events = min_events
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def push(self, envelope: EventEnvelope) -> None:
        self._buffer.append(envelope)

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self._window_seconds)
            if len(self._buffer) >= self._min_events:
                batch = self._buffer.copy()
                self._buffer.clear()
                logger.info("[window] flushing %d events", len(batch))
                try:
                    await self._on_ready(batch)
                except Exception:
                    logger.exception("[window] error in on_ready callback")
            else:
                self._buffer.clear()
