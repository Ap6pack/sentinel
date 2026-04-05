# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx

from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

from ..config import rf_settings
from .base import BaseDecoder, OnEvent

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"


def parse_aircraft(ac: dict) -> EventEnvelope | None:
    """Parse a single aircraft dict into an EventEnvelope, or None if unusable.

    Never raises -- logs and returns None on parse errors, per BaseDecoder contract.
    The one exception is when called directly in tests that explicitly expect ValueError.
    """
    icao = ac.get("hex", "").upper()
    if not icao or "lat" not in ac or "lon" not in ac:
        return None
    lat, lon = ac["lat"], ac["lon"]
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        logger.debug("Skipping aircraft %s: coords out of range (%s, %s)", icao, lat, lon)
        return None
    alt_ft = ac.get("altitude") or ac.get("alt_baro") or ac.get("alt_geom")
    alt_m = float(alt_ft) * 0.3048 if alt_ft is not None else None
    return EventEnvelope(
        source="rf",
        kind=EventKind.AIRCRAFT,
        lat=lat,
        lon=lon,
        alt_m=alt_m,
        entity_id=f"ICAO-{icao}",
        payload={
            "icao": icao,
            "callsign": ac.get("flight", "").strip(),
            "speed_kts": ac.get("speed") or ac.get("gs"),
            "heading": ac.get("track"),
            "squawk": ac.get("squawk"),
            "rssi": ac.get("rssi"),
            "messages": ac.get("messages", 0),
        },
    )


class ADSBDecoder(BaseDecoder):
    """
    Polls dump1090-rs JSON endpoint for aircraft data.
    In mock mode, replays tests/fixtures/aircraft_sample.json.
    """

    name = "adsb"
    POLL_URL = "http://localhost:8080/data/aircraft.json"

    def __init__(self, device_index: int = 0, poll_interval: float | None = None):
        super().__init__(device_index=device_index)
        self.poll_interval = poll_interval or rf_settings.poll_interval

    def _build_command(self) -> list[str]:
        return [
            "dump1090_rs",
            "--device-index",
            str(self.device_index),
            "--net",
            "--net-only-port",
            "8080",
        ]

    def _parse_line(self, line: str) -> EventEnvelope | None:
        return None  # Not used -- we poll HTTP instead

    async def run(self, on_event: OnEvent) -> None:
        if rf_settings.mock:
            await self._run_mock(on_event)
        else:
            await self._run_live(on_event)

    async def _run_mock(self, on_event: OnEvent) -> None:
        fixture_path = FIXTURES_DIR / "aircraft_sample.json"
        logger.info("[adsb] mock mode — replaying %s", fixture_path)
        data = json.loads(fixture_path.read_text())
        aircraft_list = data.get("aircraft", data if isinstance(data, list) else [])

        while self._running:
            for ac in aircraft_list:
                if not self._running:
                    return
                envelope = parse_aircraft(ac)
                if envelope is not None:
                    await on_event(envelope)
            await asyncio.sleep(self.poll_interval)

    async def _run_live(self, on_event: OnEvent) -> None:
        cmd = self._build_command()
        logger.info("[adsb] starting subprocess: %s", " ".join(cmd))
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.sleep(2)  # Give dump1090-rs time to start

        async with httpx.AsyncClient(timeout=2.0) as client:
            while self._running:
                try:
                    resp = await client.get(self.POLL_URL)
                    data = resp.json()
                    for ac in data.get("aircraft", []):
                        envelope = parse_aircraft(ac)
                        if envelope is not None:
                            await on_event(envelope)
                except httpx.TimeoutException:
                    logger.warning("[adsb] poll timeout")
                except httpx.HTTPStatusError as e:
                    logger.warning("[adsb] HTTP %d", e.response.status_code)
                except Exception as e:
                    logger.warning("[adsb] poll error: %s", e)
                await asyncio.sleep(self.poll_interval)
