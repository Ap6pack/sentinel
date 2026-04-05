# SKILL: Testing conventions — SENTINEL platform

## Purpose
Read this before writing any test, fixture, or mock. Testing conventions are
centralised here so agents do not contradict each other across modules. The
scattered testing notes in other SKILL files are summaries — this file is
the authority.

---

## Test taxonomy

| Type | Location | Runs in CI | Needs Docker | Needs hardware |
|---|---|---|---|---|
| Unit | `packages/{module}/tests/` | Yes | No | No |
| Integration | `tests/` (repo root) | Yes | Yes (mock profile) | No |
| Hardware | `tests/hardware/` | No | No | Yes (RTL-SDR) |

Never put integration tests inside a module's `tests/` directory. Never put
unit tests in the repo root `tests/` directory. The distinction matters because
CI runs `pytest packages/` for unit tests and `pytest tests/` for integration
tests with separate environment setup.

---

## Running tests

```bash
# Unit tests only (no Docker, no hardware)
pytest packages/ -x -q

# Unit tests with coverage
pytest packages/ --cov=sentinel_common --cov=sentinel_rf \
  --cov=sentinel_osint --cov=sentinel_ai \
  --cov-report=term-missing -q

# Integration tests (requires mock Docker stack running)
docker compose -f infra/docker-compose.yml --profile mock up -d
pytest tests/ -x -q -m integration

# Single module
pytest packages/sentinel-rf/ -x -q -v

# Single test file
pytest packages/sentinel-rf/tests/test_adsb_parser.py -x -v

# Single test
pytest packages/sentinel-rf/tests/test_adsb_parser.py::test_parses_valid_aircraft -xvs
```

---

## Python test stack

```toml
# pyproject.toml (each module)
[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-httpx>=0.30",    # Mock httpx.AsyncClient
    "respx>=0.20",           # Alternative httpx mock (use pytest-httpx consistently)
    "fakeredis>=2.21",       # In-memory Redis for bus tests
    "freezegun>=1.4",        # Freeze time in correlation window tests
]
```

Prefer `pytest-httpx` over `respx` — pick one and use it everywhere.
Do not mix them. The project standard is `pytest-httpx`.

---

## pytest configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"          # All async tests run automatically, no decorator needed
testpaths = ["tests"]
markers = [
    "integration: requires running Docker stack",
    "hardware: requires physical RTL-SDR device",
    "slow: takes more than 5 seconds",
]
```

With `asyncio_mode = "auto"`, write async tests as:
```python
async def test_something():   # No @pytest.mark.asyncio needed
    result = await some_async_function()
    assert result == expected
```

---

## Mocking Redis (bus tests)

Use `fakeredis` — it is a full in-memory Redis implementation that supports
Streams, consumer groups, and all commands used by `BusPublisher`/`BusConsumer`.

```python
# tests/conftest.py (module level)
import pytest
import fakeredis.aioredis as fakeredis
from sentinel_common.bus import BusPublisher, BusConsumer

@pytest.fixture
async def redis_client():
    client = fakeredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()

@pytest.fixture
async def bus_publisher(redis_client):
    pub = BusPublisher.__new__(BusPublisher)
    pub._client = redis_client
    return pub

@pytest.fixture
async def bus_consumer(redis_client):
    def make_consumer(group, consumer, kinds=None):
        c = BusConsumer.__new__(BusConsumer)
        c._client = redis_client
        c._group = group
        c._consumer = consumer
        c._kinds = set(kinds) if kinds else None
        c._stream = "sentinel:events"
        return c
    return make_consumer
```

Usage:
```python
async def test_publish_and_consume(bus_publisher, bus_consumer):
    from sentinel_common.envelope import EventEnvelope
    from sentinel_common.kinds import EventKind

    env = EventEnvelope(source="rf", kind=EventKind.AIRCRAFT,
                        lat=51.5, lon=-0.1, entity_id="TEST-1",
                        payload={"callsign": "TST001"})

    await bus_publisher.publish(env)

    consumer = bus_consumer("test-group", "test-node", kinds=["aircraft"])
    received = []
    async for event in consumer:
        received.append(event)
        break   # Stop after first event

    assert len(received) == 1
    assert received[0].entity_id == "TEST-1"
```

---

## Mocking httpx (collector and API tests)

Use `pytest-httpx` to mock all outbound HTTP calls. **Never make real HTTP
calls in unit tests.** Use `PYTEST_HTTPX_TRANSPORT` to enforce this globally.

```python
# tests/conftest.py
import pytest
from pytest_httpx import HTTPXMock

# This fixture is provided by pytest-httpx automatically
# Use it in any test that makes httpx calls:

async def test_wigle_collector(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url__startswith="https://api.wigle.net/",
        json={
            "success": True,
            "results": [
                {
                    "netid": "AA:BB:CC:DD:EE:FF",
                    "ssid": "HomeNetwork_5G",
                    "trilat": 51.5074,
                    "trilong": -0.1278,
                    "lastupdt": "2024-01-01 00:00:00",
                }
            ]
        }
    )

    from sentinel_osint.collectors.wigle import WiGLECollector
    collector = WiGLECollector()
    collector._api_key = "test-key"

    records = [r async for r in collector.collect(51.5074, -0.1278, 500)]
    assert len(records) == 1
    assert records[0].source_id == "AA:BB:CC:DD:EE:FF"
```

If a test makes an unexpected HTTP call (not mocked), `pytest-httpx` raises
`httpx.HTTPStatusError` by default — this is the correct behaviour. Never add
`allow_unmatched=True` globally.

---

## Mocking the Claude API

```python
# Use unittest.mock — do not install a separate anthropic mock library
from unittest.mock import patch, MagicMock
import json

VALID_ALERT_RESPONSE = json.dumps({
    "alert_warranted": True,
    "confidence": 0.87,
    "summary": "BSSID match detected",
    "reasoning": "RF WiFi scan BSSID matches WiGLE profile.",
    "recommended_action": "Review profile",
    "linked_entity_ids": ["WIFI-AA:BB:CC:DD:EE:FF", "profile-abc123"],
    "lat": 51.5074,
    "lon": -0.1278,
})

NO_ALERT_RESPONSE = json.dumps({
    "alert_warranted": False,
    "confidence": 0.2,
    "summary": "",
    "reasoning": "Insufficient corroborating signals.",
    "recommended_action": "",
    "linked_entity_ids": [],
    "lat": None,
    "lon": None,
})

@pytest.fixture
def mock_claude_alert():
    """Fixture that makes Claude return a high-confidence alert."""
    with patch("anthropic.Anthropic") as mock:
        msg = MagicMock()
        msg.content = [MagicMock(text=VALID_ALERT_RESPONSE)]
        mock.return_value.messages.create.return_value = msg
        yield mock

@pytest.fixture
def mock_claude_no_alert():
    """Fixture that makes Claude return no alert."""
    with patch("anthropic.Anthropic") as mock:
        msg = MagicMock()
        msg.content = [MagicMock(text=NO_ALERT_RESPONSE)]
        mock.return_value.messages.create.return_value = msg
        yield mock
```

Always test both the alert and no-alert paths. Always test the malformed JSON
path:

```python
async def test_correlator_handles_malformed_json(mock_claude_alert):
    mock_claude_alert.return_value.messages.create.return_value.content = [
        MagicMock(text="This is not JSON at all")
    ]
    from sentinel_ai.engine.correlator import correlate_batch
    result = await correlate_batch([some_event], [some_profile])
    assert result is None   # Must return None, not raise
```

---

## Decoder fixture format

Every decoder in `sentinel-rf` needs a fixture file. These are real captured
output lines from the actual CLI tools. Format per decoder:

### dump1090-rs (`fixtures/aircraft_sample.json`)
```json
{
  "now": 1704067200.0,
  "messages": 847293,
  "aircraft": [
    {
      "hex": "3c4a6f",
      "flight": "DLH441  ",
      "lat": 51.5074,
      "lon": -0.1278,
      "altitude": 35000,
      "speed": 430,
      "track": 278,
      "squawk": "1234",
      "rssi": -14.2,
      "messages": 47,
      "seen": 0.4
    }
  ]
}
```

### rtl_433 (`fixtures/rtl433_lines.txt`) — one JSON object per line
```
{"time": "2024-01-01 00:00:00", "model": "Acurite-Tower", "id": 12345, "channel": "A", "temperature_C": 18.3, "humidity": 62, "mic": "CRC"}
{"time": "2024-01-01 00:00:01", "model": "TPMS-Citroen", "id": 16773118, "type": 0, "pressure_kPa": 230.0, "temperature_C": 28.0, "flags": 128, "mic": "CRC"}
{"time": "2024-01-01 00:00:02", "model": "Oregon-CM160", "id": 62, "channel": 1, "power_W": 324, "energy_kWh": 1248.4}
```
Include at least 20 lines covering multiple device models. Include at least
one malformed line to test error handling:
```
{"time": "2024-01-01 00:00:03", "model": "Corrupt
```

### airodump-ng (`fixtures/airodump_csv_lines.txt`) — raw CSV lines
```
 BSSID, First time seen, Last time seen, channel, Speed, Privacy, Cipher, Authentication, Power, # beacons, # IV, LAN IP, ID-length, ESSID, Key
 AA:BB:CC:DD:EE:FF, 2024-01-01 00:00:00, 2024-01-01 00:01:00,  6, 130, WPA2, CCMP, PSK, -45,       47,        0,   0.0.0.0,        14, HomeNetwork_5G,
 11:22:33:44:55:66, 2024-01-01 00:00:01, 2024-01-01 00:01:01, 11,  54, OPN,     ,    , -72,       12,        0,   0.0.0.0,         9, CafeWiFi ,
```
Note: airodump-ng CSV has leading spaces in BSSID column and trailing spaces
in ESSID — your parser must strip these.

---

## Freezing time in window tests

The `EventWindow` 30-second flush depends on real time. Use `freezegun`:

```python
from freezegun import freeze_time
import asyncio

async def test_window_flushes_after_30s():
    flushed = []

    async def on_ready(batch):
        flushed.append(batch)

    window = EventWindow(on_ready)
    await window.start()

    await window.push(make_event("aircraft"))
    await window.push(make_event("wifi"))

    with freeze_time("2024-01-01 00:00:31"):
        await asyncio.sleep(0)   # Yield to let the flush task run

    assert len(flushed) == 1
    assert len(flushed[0]) == 2
```

---

## Database tests (SQLAlchemy)

Use an in-memory SQLite database for unit tests — never Postgres.

```python
# tests/conftest.py (sentinel-osint, sentinel-ai)
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sentinel_osint.models.profile import Base

@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

Never use the production Postgres URL in tests. If a test is marked
`@pytest.mark.integration` it may use Docker Postgres — but only
integration tests, never unit tests.

---

## Coverage requirements

| Module | Minimum coverage |
|---|---|
| sentinel-common | 95% |
| sentinel-rf (parsers only) | 90% |
| sentinel-osint (linker) | 85% |
| sentinel-ai (correlator) | 85% |
| sentinel-core (auth, bridge) | 80% |

CI will fail if coverage drops below these thresholds. To check:
```bash
pytest packages/sentinel-common/ --cov=sentinel_common \
  --cov-fail-under=95 -q
```

---

## What not to test

- Do not test third-party library behaviour (httpx, Pydantic, SQLAlchemy)
- Do not test that `asyncio.sleep` actually sleeps
- Do not test private methods (`_parse_line`) directly — test them through
  the public interface (`run()` or fixture replay)
- Do not write tests that pass only because they mock everything —
  at least one integration test per module must exercise the real code path
  against real Redis (via fakeredis) and real SQLite

---

## Common mistakes to avoid

- **Do not** use `@pytest.mark.asyncio` on individual tests — set
  `asyncio_mode = "auto"` in `pyproject.toml` once and forget about it
- **Do not** share state between tests via module-level variables — use
  fixtures with function scope (the default)
- **Do not** test the happy path only — every function that can return `None`
  or raise must have a test for each of those cases
- **Do not** mock at the wrong level — mock `httpx.AsyncClient` not
  `requests.get` (we use httpx, not requests)
- **Do not** write `assert response is not None` as the only assertion —
  assert the actual content
- **Do not** leave `print()` statements in tests — use `capfd` or logging
  capture if you need to inspect output
