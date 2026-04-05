# SKILL: sentinel-rf — RF/SDR signal intelligence layer

## Purpose
This skill governs all work in `packages/sentinel-rf/`. It covers how to wrap
SDR CLI tools as subprocesses, parse their output into normalised
`EventEnvelope` objects, publish to the bus, and expose the REST/WebSocket API.
Read this before touching any decoder, adding a new signal type, or changing
how subprocesses are managed.

---

## What this module does
`sentinel-rf` is the Layer 1 physical RF intelligence pipeline. It wraps the
iNTERCEPT SDR toolchain, ingests signals from attached RTL-SDR / HackRF /
Ubertooth hardware, and publishes normalised events to the shared bus. It also
runs a Flask-SocketIO server (inherited from iNTERCEPT) that provides a
standalone web UI and REST API.

This module must work **with zero internet connectivity**. Never add a network
dependency to a decoder.

---

## Repository layout

```
packages/sentinel-rf/
├── sentinel_rf/
│   ├── app.py                  # Flask-SocketIO entry point
│   ├── api/
│   │   ├── routes.py           # REST endpoints
│   │   └── health.py           # /api/v1/health
│   ├── decoders/
│   │   ├── base.py             # BaseDecoder ABC
│   │   ├── adsb.py             # dump1090-rs wrapper
│   │   ├── ais.py              # AIS-catcher wrapper
│   │   ├── wifi.py             # aircrack-ng monitor mode wrapper
│   │   ├── bluetooth.py        # BlueZ / Ubertooth wrapper
│   │   ├── rtl433.py           # rtl_433 wrapper
│   │   └── pager.py            # rtl_fm | multimon-ng wrapper
│   ├── agents/
│   │   └── remote_agent.py     # Receives events from distributed nodes
│   └── publisher.py            # Thin wrapper: decoder output → BusPublisher
├── tests/
│   ├── test_adsb_parser.py
│   └── fixtures/
│       └── aircraft_sample.json
└── pyproject.toml
```

---

## BaseDecoder — the pattern every decoder must follow

```python
# sentinel_rf/decoders/base.py
from __future__ import annotations
import asyncio
import logging
from abc import ABC, abstractmethod
from sentinel_common.envelope import EventEnvelope

logger = logging.getLogger(__name__)

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
        Never raise — log and return None on parse errors.
        """

    async def run(self, on_event) -> None:
        """
        Start the subprocess and call on_event(envelope) for each parsed line.
        Restarts automatically on exit with exponential backoff.
        """
        backoff = 1
        while self._running:
            try:
                cmd = self._build_command()
                logger.info(f"[{self.name}] starting: {' '.join(cmd)}")
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
                    except Exception as e:
                        logger.debug(f"[{self.name}] parse error: {e} | line: {line[:120]}")
                        continue
                    if envelope is not None:
                        await on_event(envelope)
            except Exception as e:
                logger.warning(f"[{self.name}] subprocess error: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    async def start(self, on_event) -> None:
        self._running = True
        asyncio.create_task(self.run(on_event))

    async def stop(self) -> None:
        self._running = False
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            await self._proc.wait()
```

---

## ADS-B decoder (dump1090-rs)

```python
# sentinel_rf/decoders/adsb.py
import json
import httpx
import asyncio
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind
from .base import BaseDecoder

class ADSBDecoder(BaseDecoder):
    """
    Polls dump1090-rs JSON endpoint rather than parsing stdout line-by-line,
    because dump1090-rs outputs a JSON file at /run/dump1090/aircraft.json
    and serves it over HTTP on port 8080.
    """
    name = "adsb"
    POLL_URL = "http://localhost:8080/data/aircraft.json"
    POLL_INTERVAL = 1.0   # seconds

    def _build_command(self) -> list[str]:
        return [
            "dump1090_rs",
            "--device-index", str(self.device_index),
            "--net",
            "--net-only-port", "8080",
        ]

    def _parse_line(self, line: str) -> EventEnvelope | None:
        return None  # Not used — we poll HTTP instead

    async def run(self, on_event) -> None:
        # Start dump1090-rs subprocess
        cmd = self._build_command()
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.sleep(2)  # Give dump1090-rs time to start

        seen: dict[str, str] = {}  # icao → last squawk, for change detection
        async with httpx.AsyncClient(timeout=2.0) as client:
            while self._running:
                try:
                    resp = await client.get(self.POLL_URL)
                    data = resp.json()
                    for ac in data.get("aircraft", []):
                        icao = ac.get("hex", "").upper()
                        if not icao or "lat" not in ac or "lon" not in ac:
                            continue
                        envelope = EventEnvelope(
                            source="rf",
                            kind=EventKind.AIRCRAFT,
                            lat=ac["lat"],
                            lon=ac["lon"],
                            alt_m=ac.get("altitude", 0) * 0.3048,  # ft → m
                            entity_id=f"ICAO-{icao}",
                            payload={
                                "icao": icao,
                                "callsign": ac.get("flight", "").strip(),
                                "speed_kts": ac.get("speed"),
                                "heading": ac.get("track"),
                                "squawk": ac.get("squawk"),
                                "rssi": ac.get("rssi"),
                                "messages": ac.get("messages", 0),
                            }
                        )
                        await on_event(envelope)
                except Exception as e:
                    import logging; logging.getLogger(__name__).warning(f"[adsb] poll error: {e}")
                await asyncio.sleep(self.POLL_INTERVAL)
```

---

## rtl_433 decoder (sensors, TPMS, IoT)

```python
# sentinel_rf/decoders/rtl433.py
import json
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind
from .base import BaseDecoder

class RTL433Decoder(BaseDecoder):
    name = "rtl433"

    def _build_command(self) -> list[str]:
        return [
            "rtl_433",
            "-d", str(self.device_index),
            "-F", "json",       # JSON output per decoded packet
            "-M", "level",      # Include signal level
        ]

    def _parse_line(self, line: str) -> EventEnvelope | None:
        data = json.loads(line)
        # rtl_433 JSON always has "model" and "time"
        model = data.get("model", "unknown")
        # Only emit if we have location (GPS-tagged dongle) or it's a TPMS
        lat = data.get("lat")
        lon = data.get("lon")
        return EventEnvelope(
            source="rf",
            kind=EventKind.WIFI,  # Reuse WIFI kind for generic 433MHz; add SENSOR kind if needed
            lat=lat,
            lon=lon,
            entity_id=f"433-{model}-{data.get('id', 'unknown')}",
            payload=data,
        )
```

---

## WiFi decoder (aircrack-ng monitor mode)

```python
# sentinel_rf/decoders/wifi.py
import re, subprocess
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind
from .base import BaseDecoder

class WiFiDecoder(BaseDecoder):
    """
    Uses airodump-ng in CSV output mode. Requires WiFi adapter in monitor mode.
    Run `airmon-ng start wlan0` before starting this decoder.
    """
    name = "wifi"

    def __init__(self, interface: str = "wlan0mon", **kwargs):
        super().__init__(**kwargs)
        self.interface = interface

    def _build_command(self) -> list[str]:
        return [
            "airodump-ng",
            "--output-format", "csv",
            "--write", "/tmp/sentinel_wifi",
            "--write-interval", "2",
            self.interface,
        ]

    def _parse_line(self, line: str) -> EventEnvelope | None:
        # airodump-ng CSV lines: BSSID, FirstTimeSeen, LastTimeSeen, channel,
        # Speed, Privacy, Cipher, Auth, Power, Beacons, IV, LanIP, IDLength, ESSID, Key
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 14:
            return None
        bssid = parts[0]
        if not re.match(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", bssid):
            return None
        ssid = parts[13] if len(parts) > 13 else ""
        power = parts[8]
        return EventEnvelope(
            source="rf",
            kind=EventKind.WIFI,
            entity_id=f"WIFI-{bssid}",
            payload={
                "bssid": bssid,
                "ssid": ssid,
                "channel": parts[3],
                "power_dbm": power,
                "privacy": parts[5],
            }
        )
```

**Important:** WiFi events frequently lack lat/lon. The publisher layer
enriches them with the current GPS position from gpsd before putting them
on the bus. See `publisher.py`.

---

## Publisher — GPS enrichment before bus publish

```python
# sentinel_rf/publisher.py
import asyncio, logging
import gpsd
from sentinel_common.bus import BusPublisher
from sentinel_common.envelope import EventEnvelope

logger = logging.getLogger(__name__)

class RFPublisher:
    def __init__(self, bus: BusPublisher):
        self._bus = bus
        self._gps_lat: float | None = None
        self._gps_lon: float | None = None

    async def start_gps_poll(self):
        """Poll gpsd every 5s and cache current position."""
        try:
            gpsd.connect()
        except Exception:
            logger.warning("gpsd not available — events will lack GPS coordinates")
            return
        while True:
            try:
                packet = gpsd.get_current()
                if packet.mode >= 2:
                    self._gps_lat = packet.lat
                    self._gps_lon = packet.lon
            except Exception:
                pass
            await asyncio.sleep(5)

    async def publish(self, envelope: EventEnvelope) -> None:
        # Enrich with GPS if event lacks coords and we have a fix
        if envelope.lat is None and self._gps_lat is not None:
            envelope = envelope.model_copy(update={
                "lat": self._gps_lat,
                "lon": self._gps_lon,
            })
        await self._bus.publish(envelope)
```

---

## REST API endpoints

All endpoints return JSON. Health is the most important — sentinel-core polls it.

```python
# sentinel_rf/api/health.py
from fastapi import APIRouter
from sentinel_rf.decoders import registry  # dict[str, BaseDecoder]

router = APIRouter()

@router.get("/api/v1/health")
async def health():
    return {
        "module": "sentinel-rf",
        "status": "ok",
        "decoders": {
            name: {
                "running": dec._running,
                "pid": dec._proc.pid if dec._proc else None,
            }
            for name, dec in registry.items()
        }
    }

@router.get("/api/v1/aircraft")
async def aircraft():
    """Latest aircraft snapshot from dump1090-rs."""
    import httpx
    async with httpx.AsyncClient(timeout=2.0) as c:
        r = await c.get("http://localhost:8080/data/aircraft.json")
        return r.json()
```

---

## Adding a new decoder — checklist

1. Create `sentinel_rf/decoders/{name}.py` extending `BaseDecoder`
2. Implement `_build_command()` and `_parse_line()` (or override `run()` for
   poll-based decoders like ADS-B)
3. Add the new `EventKind` to `sentinel_common/kinds.py` if needed
4. Register it in `sentinel_rf/decoders/__init__.py` registry dict
5. Add a fixture file in `tests/fixtures/` with 20+ real sample output lines
6. Write `tests/test_{name}_parser.py` with at least 5 parse cases including
   one malformed-input test that confirms `_parse_line` returns `None` gracefully
7. Document the hardware requirement in `docs/HARDWARE.md`

---

## Subprocess management rules

- Always use `asyncio.create_subprocess_exec` (never `subprocess.Popen`) —
  blocking subprocess calls will stall the event loop
- Always set `stderr=asyncio.subprocess.DEVNULL` unless debugging — noisy
  stderr fills logs and hides real errors
- Always implement restart-with-backoff (built into `BaseDecoder.run`)
- Never shell=True — always pass argv list to avoid injection
- Always call `decoder.stop()` in the FastAPI/Flask shutdown hook — orphaned
  rtl_fm or dump1090 processes hold the USB device and block restarts

---

## Hardware device index

If multiple RTL-SDR dongles are attached, each decoder is initialised with a
`device_index`. Convention:

| Index | Dedicated use |
|---|---|
| 0 | ADS-B (1090 MHz) |
| 1 | AIS + 433MHz (dual-purpose with frequency hop) |
| 2 | Wideband scanner / pager |

Document this in `.env.example` as `SENTINEL_ADSB_DEVICE_INDEX=0` etc.

---

## Testing without hardware

Set `SENTINEL_RF_MOCK=true` in `.env`. Each decoder checks this flag and,
when set, replays the corresponding fixture file in a loop at 1x speed instead
of starting the real subprocess. This enables full CI testing without SDR
hardware attached.

```python
import os
MOCK_MODE = os.getenv("SENTINEL_RF_MOCK", "false").lower() == "true"
```
