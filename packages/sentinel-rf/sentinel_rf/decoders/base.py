# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import Any

from sentinel_common.envelope import EventEnvelope

logger = logging.getLogger(__name__)

OnEvent = Callable[[EventEnvelope], Coroutine[Any, Any, None]]


class BaseDecoder(ABC):
    """
    Manages a long-running subprocess and emits EventEnvelopes.
    Subclasses implement `_build_command` and `_parse_line`.
    """

    name: str = "base"

    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self._proc: asyncio.subprocess.Process | None = None
        self._running = False

    @abstractmethod
    def _build_command(self) -> list[str]:
        """Return the argv list for subprocess.create_subprocess_exec."""

    @abstractmethod
    def _parse_line(self, line: str) -> EventEnvelope | None:
        """
        Parse one line of stdout from the subprocess.
        Return an EventEnvelope or None if the line should be skipped.
        Never raise -- log and return None on parse errors.
        """

    async def run(self, on_event: OnEvent) -> None:
        """
        Start the subprocess and call on_event(envelope) for each parsed line.
        Restarts automatically on exit with exponential backoff.
        """
        backoff = 1
        while self._running:
            try:
                cmd = self._build_command()
                logger.info("[%s] starting: %s", self.name, " ".join(cmd))
                self._proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                backoff = 1
                async for raw in self._proc.stdout:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        envelope = self._parse_line(line)
                    except Exception:
                        logger.debug(
                            "[%s] parse error on line: %s", self.name, line[:120]
                        )
                        continue
                    if envelope is not None:
                        await on_event(envelope)
            except Exception as e:
                logger.warning("[%s] subprocess error: %s", self.name, e)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    async def start(self, on_event: OnEvent) -> None:
        self._running = True
        asyncio.create_task(self.run(on_event))

    async def stop(self) -> None:
        self._running = False
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            await self._proc.wait()
