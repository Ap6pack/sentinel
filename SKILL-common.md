# SKILL: sentinel-common — Shared contracts & event bus

## Purpose
This skill governs all work in `packages/sentinel-common/` and any code that
publishes to or consumes from the Redis Streams event bus. Read this before
touching the envelope schema, adding a new event kind, or wiring a new module
into the bus.

---

## The golden rule
**No module may import another module directly.**
All inter-module communication goes through the event bus or the REST API
contracts defined in this skill. If you find yourself writing
`from sentinel_rf import ...` inside `sentinel_osint`, stop and use the bus.

---

## Repository layout

```
packages/sentinel-common/
├── sentinel_common/
│   ├── __init__.py
│   ├── envelope.py        # EventEnvelope Pydantic model — single source of truth
│   ├── bus.py             # BusPublisher and BusConsumer wrappers
│   ├── kinds.py           # EventKind enum — all valid event kind strings
│   ├── geo.py             # Shared geo helpers (bbox, haversine, coord validation)
│   └── config.py          # Settings model (reads .env via pydantic-settings)
├── tests/
│   ├── test_envelope.py
│   └── test_bus.py
└── pyproject.toml
```

---

## EventEnvelope — the canonical schema

```python
# sentinel_common/envelope.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator

class EventEnvelope(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str                          # "rf" | "osint" | "ai" | "core"
    kind: str                            # see EventKind enum
    lat: Optional[float] = None          # WGS-84 decimal degrees
    lon: Optional[float] = None
    alt_m: Optional[float] = None        # metres above sea level
    entity_id: str                       # stable ID for this entity across events
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_coords(self) -> EventEnvelope:
        if self.lat is not None and not (-90 <= self.lat <= 90):
            raise ValueError(f"lat out of range: {self.lat}")
        if self.lon is not None and not (-180 <= self.lon <= 180):
            raise ValueError(f"lon out of range: {self.lon}")
        return self

    def to_redis(self) -> dict[str, str]:
        """Serialise for Redis XADD — all values must be strings."""
        return {"data": self.model_dump_json()}

    @classmethod
    def from_redis(cls, fields: dict[str, str]) -> EventEnvelope:
        return cls.model_validate_json(fields["data"])
```

**Never add new top-level fields to EventEnvelope without a version bump.**
All module-specific data goes into `payload`. If a field is needed by more than
two modules it can be promoted to top-level in a minor version bump — open a PR,
don't just add it.

---

## EventKind enum

```python
# sentinel_common/kinds.py
from enum import StrEnum

class EventKind(StrEnum):
    # Layer 1 — RF
    AIRCRAFT    = "aircraft"
    VESSEL      = "vessel"
    WIFI        = "wifi"
    BLUETOOTH   = "bluetooth"
    PAGER       = "pager"
    APRS        = "aprs"
    WEATHER_SAT = "weather_sat"

    # Layer 2 — OSINT
    PROFILE     = "profile"
    PROFILE_LINK = "profile_link"   # two entity_ids linked with confidence score

    # Layer 3 — AI
    ALERT       = "alert"
    CORRELATION = "correlation"

    # System
    HEARTBEAT   = "heartbeat"       # emitted by each module every 30s
    HEALTH      = "health"          # response to /api/v1/health poll
```

When adding a new kind: add it here first, commit, then add the producer.
Never hardcode kind strings as raw strings in module code — always use
`EventKind.AIRCRAFT`, not `"aircraft"`.

---

## BusPublisher — how to publish events

```python
# sentinel_common/bus.py
import redis.asyncio as redis
from .envelope import EventEnvelope

STREAM_NAME = "sentinel:events"
MAX_LEN = 50_000   # ~50k events in stream before trimming

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

    async def close(self):
        await self._client.aclose()
```

Usage pattern in a FastAPI lifespan:

```python
from contextlib import asynccontextmanager
from sentinel_common.bus import BusPublisher
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

publisher: BusPublisher | None = None

@asynccontextmanager
async def lifespan(app):
    global publisher
    publisher = BusPublisher()
    yield
    await publisher.close()

# In a route or background task:
await publisher.publish(EventEnvelope(
    source="rf",
    kind=EventKind.AIRCRAFT,
    lat=51.5074,
    lon=-0.1278,
    alt_m=3200,
    entity_id="ICAO-3C4A6F",
    payload={"callsign": "DLH441", "speed_kts": 430, "heading": 278}
))
```

---

## BusConsumer — how to consume events

```python
# sentinel_common/bus.py (continued)
import asyncio

class BusConsumer:
    def __init__(
        self,
        group: str,
        consumer: str,
        kinds: list[str] | None = None,   # None = all kinds
        redis_url: str = "redis://localhost:6379",
    ):
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._group = group
        self._consumer = consumer
        self._kinds = set(kinds) if kinds else None
        self._stream = STREAM_NAME

    async def ensure_group(self):
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
                self._group, self._consumer,
                {self._stream: ">"}, count=100, block=1000
            )
            for _, messages in (results or []):
                for msg_id, fields in messages:
                    envelope = EventEnvelope.from_redis(fields)
                    if self._kinds is None or envelope.kind in self._kinds:
                        yield envelope
                    await self._client.xack(self._stream, self._group, msg_id)
```

Usage:

```python
consumer = BusConsumer(
    group="sentinel-viz-consumer",
    consumer="viz-node-1",
    kinds=["aircraft", "alert"],
)
async for event in consumer:
    await websocket_broadcast(event.model_dump_json())
```

---

## Config — shared settings

```python
# sentinel_common/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class SentinelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SENTINEL_")

    redis_url: str = "redis://localhost:6379"
    postgres_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel"
    log_level: str = "INFO"
    default_lat: float = 51.5074
    default_lon: float = -0.1278

settings = SentinelSettings()
```

All modules import `from sentinel_common.config import settings`. Never
hardcode URLs or credentials in module code.

---

## Geo helpers

```python
# sentinel_common/geo.py
import math

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Returns distance in metres between two WGS-84 coordinates."""
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def bbox_contains(lat: float, lon: float, bbox: tuple[float,float,float,float]) -> bool:
    """bbox = (min_lat, min_lon, max_lat, max_lon)"""
    return bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3]
```

---

## Testing conventions

- Every envelope mutation must have a unit test in `tests/test_envelope.py`
- Bus publish/consume must be tested against a real Redis instance using
  `pytest-asyncio` and a `redis` fixture that flushes the test stream after
  each test
- Never mock the envelope schema in tests — always construct real
  `EventEnvelope` objects

```python
# tests/test_envelope.py
import pytest
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

def test_roundtrip_redis():
    env = EventEnvelope(source="rf", kind=EventKind.AIRCRAFT,
                        lat=51.5, lon=-0.1, entity_id="TEST-1",
                        payload={"callsign": "TST001"})
    raw = env.to_redis()
    restored = EventEnvelope.from_redis(raw)
    assert restored.entity_id == env.entity_id
    assert restored.payload["callsign"] == "TST001"

def test_invalid_lat():
    with pytest.raises(ValueError):
        EventEnvelope(source="rf", kind=EventKind.AIRCRAFT,
                      lat=200.0, lon=0.0, entity_id="BAD")
```

---

## Version bumping rules

| Change type | Version bump |
|---|---|
| New `EventKind` value | Patch |
| New optional field in `payload` convention | Patch |
| New required top-level field on `EventEnvelope` | Minor |
| Rename or remove existing field | Major |

Pin all modules to the same `sentinel-common` version in their
`pyproject.toml`. A major version bump requires coordinated update of all
consumers before deploying.

---

## Common mistakes to avoid

- **Do not** use `json.dumps` to serialise envelopes — always use
  `model_dump_json()` which handles datetime serialisation correctly
- **Do not** catch `redis.ResponseError` silently — log and re-raise
- **Do not** set `block=0` on `xreadgroup` in production — use `block=1000`
  (1s) so the consumer loop can be cancelled cleanly on shutdown
- **Do not** create a new Redis client per event — share a single client
  instance per process via the lifespan pattern above
- **Do not** filter events by kind inside Redis — filter in the consumer
  after deserialisation so the stream stays a single unified log
