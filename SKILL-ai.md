# SKILL: sentinel-ai — AI correlation engine

## Purpose
This skill governs all work in `packages/sentinel-ai/`. It covers how the
correlation engine consumes events from the bus, how it uses the Claude API for
multi-source reasoning, how it produces alerts, and how to write effective
prompts for intelligence correlation tasks. Read this before touching the
correlation logic, adding a new link type, or changing how alerts are generated.

---

## What this module does
`sentinel-ai` is the cross-layer intelligence engine. It consumes all events
from the Redis Streams bus, runs spatial and identifier joins against the OSINT
profile store, and uses the Claude API to synthesise multi-source observations
into coherent alerts with confidence scores and recommended operator actions.
Alerts are published back to the bus as `EventKind.ALERT` events and persisted
to Postgres.

---

## Repository layout

```
packages/sentinel-ai/
├── sentinel_ai/
│   ├── app.py                  # FastAPI entry point
│   ├── api/
│   │   ├── routes.py           # GET /alerts, POST /correlate, GET /health
│   │   └── health.py
│   ├── engine/
│   │   ├── consumer.py         # Bus event consumer loop
│   │   ├── window.py           # Sliding time window batcher
│   │   ├── spatial.py          # Spatial join: RF events ↔ OSINT profiles
│   │   ├── identifier.py       # Identifier match: BSSID/username/SSID lookups
│   │   └── correlator.py       # Claude API call + alert generation
│   ├── models/
│   │   └── alert.py            # Alert ORM model
│   └── prompts/
│       ├── correlate.txt       # System prompt for correlation reasoning
│       └── summarise.txt       # System prompt for alert summarisation
├── tests/
│   ├── test_spatial.py
│   ├── test_correlator.py
│   └── fixtures/
└── pyproject.toml
```

---

## Event consumption and windowing

The engine batches incoming events into 30-second windows before running
correlation. This prevents flooding the Claude API with single-event calls.

```python
# sentinel_ai/engine/window.py
import asyncio
from collections import defaultdict
from sentinel_common.envelope import EventEnvelope

WINDOW_SECONDS = 30
MIN_EVENTS_TO_CORRELATE = 2   # Don't call Claude for a window with a single event

class EventWindow:
    def __init__(self, on_window_ready):
        self._buffer: list[EventEnvelope] = []
        self._on_ready = on_window_ready
        self._task = None

    async def start(self):
        self._task = asyncio.create_task(self._flush_loop())

    async def push(self, envelope: EventEnvelope):
        self._buffer.append(envelope)

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(WINDOW_SECONDS)
            if len(self._buffer) >= MIN_EVENTS_TO_CORRELATE:
                batch = self._buffer.copy()
                self._buffer.clear()
                await self._on_ready(batch)
            else:
                self._buffer.clear()
```

---

## Spatial join — RF events ↔ OSINT profiles

```python
# sentinel_ai/engine/spatial.py
import httpx
from sentinel_common.envelope import EventEnvelope
from sentinel_common.geo import haversine_m

OSINT_API = "http://localhost:5001"
SPATIAL_RADIUS_M = 150   # Look for profiles within 150m of an RF event

async def find_nearby_profiles(envelope: EventEnvelope) -> list[dict]:
    """
    Query sentinel-osint for profiles near the event's coordinates.
    Returns empty list if event has no coordinates or OSINT is unreachable.
    """
    if envelope.lat is None or envelope.lon is None:
        return []
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                f"{OSINT_API}/api/v1/profiles",
                params={"lat": envelope.lat, "lon": envelope.lon,
                        "radius_m": SPATIAL_RADIUS_M},
                headers={"Authorization": f"Bearer {_get_internal_token()}"},
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        import logging; logging.getLogger(__name__).warning(f"[spatial] {e}")
        return []
```

---

## Identifier match — BSSID/SSID linking

When a `wifi` event arrives on the bus, immediately check whether the BSSID or
SSID matches any OSINT profile — this is a high-confidence link that does not
need to wait for the 30-second window.

```python
# sentinel_ai/engine/identifier.py
import httpx

async def match_wifi_to_profile(bssid: str, ssid: str) -> dict | None:
    """
    Returns the matching profile if the BSSID or SSID is known to OSINT.
    """
    async with httpx.AsyncClient(timeout=5) as c:
        try:
            r = await c.get(
                f"{OSINT_API}/api/v1/profiles",
                params={"identifier_bssid": bssid},
                headers={"Authorization": f"Bearer {_get_internal_token()}"},
            )
            profiles = r.json()
            if profiles:
                return profiles[0]
            # Fall back to SSID match (lower confidence)
            r2 = await c.get(
                f"{OSINT_API}/api/v1/profiles",
                params={"identifier_ssid": ssid},
                headers={"Authorization": f"Bearer {_get_internal_token()}"},
            )
            return r2.json()[0] if r2.json() else None
        except Exception:
            return None
```

---

## Correlator — Claude API reasoning

```python
# sentinel_ai/engine/correlator.py
import anthropic, json, logging
from sentinel_common.envelope import EventEnvelope, EventKind
from sentinel_ai.models.alert import AlertRecord
import uuid

logger = logging.getLogger(__name__)
client = anthropic.Anthropic()

SYSTEM_PROMPT = open("sentinel_ai/prompts/correlate.txt").read()

async def correlate_batch(
    events: list[EventEnvelope],
    profiles: list[dict],
) -> AlertRecord | None:
    """
    Given a batch of events and any matching profiles, call Claude to reason
    about whether an alert should be raised. Returns None if no alert warranted.
    """
    if not profiles:
        return None  # No profiles matched — nothing to correlate

    # Build the context payload for Claude
    context = {
        "events": [
            {
                "kind": e.kind,
                "ts": e.ts.isoformat(),
                "lat": e.lat,
                "lon": e.lon,
                "entity_id": e.entity_id,
                "payload": e.payload,
            }
            for e in events
        ],
        "profiles": profiles,
    }

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Analyse this observation batch and profiles:\n\n{json.dumps(context, indent=2)}"
            }]
        )
        raw = response.content[0].text

        # Expect Claude to return JSON — see prompt for schema
        result = json.loads(raw)

        if not result.get("alert_warranted", False):
            return None

        return AlertRecord(
            id=str(uuid.uuid4()),
            confidence=float(result.get("confidence", 0.5)),
            summary=result.get("summary", ""),
            reasoning=result.get("reasoning", ""),
            recommended_action=result.get("recommended_action", ""),
            linked_entity_ids=result.get("linked_entity_ids", []),
            lat=result.get("lat"),
            lon=result.get("lon"),
            event_ids=[str(e.id) for e in events],
        )

    except json.JSONDecodeError:
        logger.warning("[correlator] Claude response was not valid JSON")
        return None
    except Exception as e:
        logger.error(f"[correlator] Claude API error: {e}")
        return None
```

---

## System prompt (correlate.txt)

This is the most important file in sentinel-ai. Keep it version-controlled and
treat changes with the same care as schema changes.

```
You are a signal intelligence analyst assistant for the SENTINEL platform.
You will receive a JSON object containing:
- "events": a list of recent RF and OSINT events from sensors
- "profiles": a list of OSINT identity profiles that spatially or identifier-match the events

Your task is to determine whether the combination of events and profiles
constitutes a meaningful intelligence correlation that warrants an alert.

You must respond with ONLY valid JSON in this exact schema — no preamble, no
markdown, no explanation outside the JSON:

{
  "alert_warranted": boolean,
  "confidence": float (0.0–1.0),
  "summary": "One sentence describing what was observed",
  "reasoning": "2-3 sentences explaining the correlation logic",
  "recommended_action": "One sentence suggesting what the operator should do",
  "linked_entity_ids": ["entity_id_1", "entity_id_2"],
  "lat": float or null,
  "lon": float or null
}

Rules:
- Only set alert_warranted=true when confidence >= 0.6
- confidence should reflect: source quality, number of corroborating signals,
  spatial precision, and recency of the match
- A BSSID match between a WiFi RF event and an OSINT profile warrants high
  confidence (0.85+) if the BSSID appears in both within the last 5 minutes
- A spatial match alone (event within 150m of profile home coord) warrants
  medium confidence (0.5–0.7) depending on how many events corroborate it
- Never speculate beyond what the data supports
- lat/lon should be the best-known location of the correlation, not the profile home
```

**Prompt engineering rules:**
- Always instruct Claude to return JSON-only — no prose wrappers
- Always define the exact JSON schema in the prompt — don't rely on Claude inferring it
- Always specify the confidence scoring rubric explicitly
- Test prompt changes with at least 10 fixture cases before deploying
- Keep the prompt under 500 tokens to leave room for the context payload

---

## Alert model

```python
# sentinel_ai/models/alert.py
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, JSON, Boolean
from sentinel_osint.models.profile import Base  # Shared Base from common models

class AlertRecord(Base):
    __tablename__ = "alerts"

    id                 = Column(String, primary_key=True)
    confidence         = Column(Float)
    summary            = Column(String)
    reasoning          = Column(String)
    recommended_action = Column(String)
    linked_entity_ids  = Column(JSON)    # list of entity_id strings
    lat                = Column(Float)
    lon                = Column(Float)
    event_ids          = Column(JSON)    # list of EventEnvelope IDs
    acknowledged       = Column(Boolean, default=False)
    created_at         = Column(DateTime, default=datetime.utcnow)
```

After persisting an alert, publish it to the bus:

```python
await publisher.publish(EventEnvelope(
    source="ai",
    kind=EventKind.ALERT,
    lat=alert.lat,
    lon=alert.lon,
    entity_id=alert.id,
    payload={
        "confidence": alert.confidence,
        "summary": alert.summary,
        "reasoning": alert.reasoning,
        "recommended_action": alert.recommended_action,
        "linked_entity_ids": alert.linked_entity_ids,
    }
))
```

---

## API endpoints

```python
# sentinel_ai/api/routes.py
from fastapi import APIRouter, Query
router = APIRouter()

@router.get("/api/v1/alerts")
async def list_alerts(
    acknowledged: bool = Query(False),
    limit: int = Query(50),
):
    """Returns active alerts. Used by sentinel-viz AlertDrawer."""
    ...

@router.post("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Mark an alert as acknowledged by the operator."""
    ...

@router.post("/api/v1/correlate")
async def force_correlate(lat: float, lon: float, radius_m: float = 500):
    """Trigger immediate correlation for a geographic area on demand."""
    ...
```

---

## Testing the correlation engine

Never use real API calls in tests. Use `pytest-httpx` to mock the OSINT API
and `anthropic`'s test utilities (or a mock) for Claude.

```python
# tests/test_correlator.py
import pytest
from sentinel_ai.engine.correlator import correlate_batch
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind
from unittest.mock import patch, MagicMock

MOCK_CLAUDE_RESPONSE = json.dumps({
    "alert_warranted": True,
    "confidence": 0.87,
    "summary": "WiFi BSSID from RF scan matches known OSINT profile home network",
    "reasoning": "BSSID AA:BB:CC:DD:EE:FF detected by SDR at 51.5074,-0.1278 matches WiGLE record linked to profile-abc123. Signal detected within 2 minutes of profile last-seen timestamp.",
    "recommended_action": "Review profile-abc123 and cross-reference with recent ADS-B tracks in the area",
    "linked_entity_ids": ["WIFI-AA:BB:CC:DD:EE:FF", "profile-abc123"],
    "lat": 51.5074,
    "lon": -0.1278,
})

@pytest.mark.asyncio
async def test_wifi_bssid_alert():
    wifi_event = EventEnvelope(
        source="rf", kind=EventKind.WIFI,
        lat=51.5074, lon=-0.1278,
        entity_id="WIFI-AA:BB:CC:DD:EE:FF",
        payload={"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "HomeNetwork_5G"},
    )
    profile = {
        "entity_id": "profile-abc123",
        "lat": 51.5075, "lon": -0.1279,
        "identifiers": {"bssid": "AA:BB:CC:DD:EE:FF"},
    }

    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=MOCK_CLAUDE_RESPONSE)]
        mock_anthropic.return_value.messages.create.return_value = mock_msg
        alert = await correlate_batch([wifi_event], [profile])

    assert alert is not None
    assert alert.confidence >= 0.8
    assert "profile-abc123" in alert.linked_entity_ids
```

---

## Cost management

Claude API calls cost real money. Implement these controls:

```python
# sentinel_ai/engine/correlator.py
import os
MAX_CALLS_PER_HOUR = int(os.getenv("SENTINEL_AI_MAX_CALLS_PER_HOUR", "100"))
_call_count = 0
_hour_start = time.monotonic()

def _check_rate_limit():
    global _call_count, _hour_start
    elapsed = time.monotonic() - _hour_start
    if elapsed > 3600:
        _call_count = 0
        _hour_start = time.monotonic()
    if _call_count >= MAX_CALLS_PER_HOUR:
        raise RuntimeError(f"Claude API rate limit reached ({MAX_CALLS_PER_HOUR}/hr)")
    _call_count += 1
```

Typical cost at 100 calls/hour with 1k input + 500 output tokens each:
~$0.40/hr on claude-sonnet-4-6. Set `SENTINEL_AI_MAX_CALLS_PER_HOUR` accordingly.

---

## Common mistakes to avoid

- **Do not** call the Claude API for single-event windows — always batch
- **Do not** pass raw `EventEnvelope` objects to Claude — serialise to plain
  dicts first and omit fields that are not relevant to the reasoning
- **Do not** trust Claude's JSON output without catching `json.JSONDecodeError`
- **Do not** include full raw OSINT records in the Claude context — summarise
  to the fields relevant to the correlation to save tokens and reduce noise
- **Do not** hard-code confidence thresholds in multiple places — define them
  once as module-level constants
- **Do not** acknowledge alerts programmatically — always require explicit
  operator action via the `/acknowledge` endpoint
