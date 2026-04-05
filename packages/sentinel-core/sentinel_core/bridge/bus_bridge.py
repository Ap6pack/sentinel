# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as redis
from fastapi import WebSocket

STREAM = "sentinel:events"

logger = logging.getLogger(__name__)


class BusBridge:
    """Reads from Redis Streams and fans out to connected WebSocket clients."""

    def __init__(self, redis_url: str):
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._clients: dict[str, tuple[WebSocket, dict]] = {}

    async def connect(self, ws: WebSocket, client_id: str) -> None:
        """Accept a WebSocket and optionally receive a filter spec."""
        await ws.accept()
        self._clients[client_id] = (ws, {})
        logger.info(
            "[bridge] client %s connected (%d total)", client_id, len(self._clients)
        )
        try:
            msg = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
            if msg.get("type") == "filter":
                self._clients[client_id] = (ws, msg.get("spec", {}))
                logger.info("[bridge] client %s filter: %s", client_id, msg.get("spec"))
        except asyncio.TimeoutError:
            pass  # No filter spec — forward everything
        except Exception:
            pass  # Client disconnected before sending filter

    def disconnect(self, client_id: str) -> None:
        self._clients.pop(client_id, None)
        logger.info("[bridge] client %s disconnected", client_id)

    def _matches_filter(self, envelope: dict, spec: dict) -> bool:
        if not spec:
            return True
        kinds = spec.get("kinds")
        if kinds and envelope.get("kind") not in kinds:
            return False
        bbox = spec.get("bbox")
        if bbox:
            lat, lon = envelope.get("lat"), envelope.get("lon")
            if lat is None or lon is None:
                return True  # No coordinates — don't filter out
            if not (bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3]):
                return False
        return True

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def broadcast_loop(self) -> None:
        """Main loop — reads from Redis Streams and fans out to WebSocket clients."""
        last_id = "$"  # Only new messages
        logger.info("[bridge] broadcast loop started, reading from %s", STREAM)
        while True:
            try:
                results = await self._redis.xread(
                    {STREAM: last_id}, count=100, block=500
                )
                for _, messages in results or []:
                    for msg_id, fields in messages:
                        last_id = msg_id
                        try:
                            envelope = json.loads(fields["data"])
                        except Exception:
                            continue
                        dead = []
                        for cid, (ws, spec) in list(self._clients.items()):
                            if self._matches_filter(envelope, spec):
                                try:
                                    await ws.send_json(envelope)
                                except Exception:
                                    dead.append(cid)
                        for cid in dead:
                            self.disconnect(cid)
            except Exception as e:
                logger.warning("[bridge] Redis error: %s", e)
                await asyncio.sleep(2)
