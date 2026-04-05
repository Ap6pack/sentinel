# SKILL: Phase verification — how to confirm a milestone is genuinely complete

## Purpose
Agents declare milestones done when they *look* done. This file defines what
"done" actually means for each milestone — specific commands to run, exact
output to expect, and failure modes that indicate the milestone is not complete
even if it appears to be working.

Do not mark a milestone complete until every check in its section passes.

---

## M0 — Monorepo running

**What this milestone means:** Docker Compose baseline is up. Redis and
Postgres are healthy. A mock event can be published and consumed. All
packages install without errors.

### Checks

```bash
# 1. All packages install cleanly
source .venv/bin/activate
pip install -e packages/sentinel-common -e packages/sentinel-rf \
  -e packages/sentinel-osint -e packages/sentinel-ai \
  -e packages/sentinel-core -q
echo "Exit code: $?"
# Expected: Exit code: 0

# 2. Import check — catches circular imports and missing dependencies
python -c "
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind
from sentinel_common.bus import BusPublisher, BusConsumer
from sentinel_common.geo import haversine_m
print('sentinel-common: OK')
"
# Expected: sentinel-common: OK

# 3. Docker stack starts
docker compose -f infra/docker-compose.yml --profile basic up -d
sleep 5
docker compose -f infra/docker-compose.yml ps
# Expected: redis and sentinel-core show "running (healthy)"
# NOT acceptable: "starting", "exited", "unhealthy"

# 4. Redis responds
redis-cli ping
# Expected: PONG

# 5. End-to-end mock event flows through the bus
python -c "
import asyncio
from sentinel_common.bus import BusPublisher, BusConsumer
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

async def test():
    pub = BusPublisher()
    await pub.publish(EventEnvelope(
        source='rf', kind=EventKind.HEARTBEAT,
        entity_id='test-m0', payload={'test': True}
    ))
    consumer = BusConsumer('m0-test', 'm0-node', kinds=['heartbeat'])
    async for event in consumer:
        assert event.entity_id == 'test-m0'
        print('Bus round-trip: OK')
        break
    await pub.close()

asyncio.run(test())
"
# Expected: Bus round-trip: OK

# 6. All unit tests pass
pytest packages/ -x -q
# Expected: all tests pass, no errors
```

**M0 is NOT complete if:**
- Any Docker service shows as "exited" or "unhealthy"
- The bus round-trip test fails or hangs
- Any package produces an ImportError

---

## M1 — RF standalone

**What this milestone means:** sentinel-rf is running at localhost:5050.
With a real RTL-SDR attached, aircraft appear on sentinel-rf's own Leaflet
map. Without hardware, mock mode produces aircraft events.

### Checks

```bash
# 1. sentinel-rf health endpoint responds
curl -s http://localhost:5050/api/v1/health | python3 -m json.tool
# Expected: JSON with "status": "ok" and decoders section

# 2. dump1090-rs subprocess is running
curl -s http://localhost:5050/api/v1/health | python3 -c "
import sys, json
h = json.load(sys.stdin)
adsb = h['decoders']['adsb']
print(f'ADS-B decoder running: {adsb[\"running\"]}')
print(f'PID: {adsb[\"pid\"]}')
assert adsb['running'], 'ADS-B decoder not running'
print('OK')
"
# Expected: running: true, PID is a number

# 3. Aircraft data is being received (with real hardware)
curl -s http://localhost:8080/data/aircraft.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
count = len(d['aircraft'])
print(f'Aircraft in range: {count}')
# Note: 0 is acceptable if you are in a low-traffic area.
# Verify by running for 5 minutes and checking again.
"

# 4. Events are reaching Redis (with real hardware or mock)
sleep 10
redis-cli XLEN sentinel:events
# Expected: > 0 (events are accumulating)

redis-cli XRANGE sentinel:events - + COUNT 5
# Expected: at least one entry with '"kind": "aircraft"'
# If only heartbeat events: dump1090-rs is running but receiving no signals

# 5. Standalone UI loads
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/
# Expected: 200
```

**Mock mode check (no hardware):**
```bash
SENTINEL_RF_MOCK=true docker compose restart sentinel-rf
sleep 5
redis-cli XRANGE sentinel:events - + COUNT 3 | grep aircraft
# Expected: aircraft events from fixture replay
```

**M1 is NOT complete if:**
- Health endpoint returns anything other than `"status": "ok"`
- No events reach Redis after 60 seconds (with hardware or mock mode)
- The standalone UI at :5050 returns a non-200 response

---

## M2 — Globe standalone

**What this milestone means:** CesiumJS globe is running at localhost:3000.
The OpenSky fallback is showing live aircraft. The satellite layer loads
TLE data and shows orbiting satellites.

### Checks

```bash
# 1. Dev server starts
cd packages/sentinel-viz && npm run dev &
sleep 5
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/
# Expected: 200

# 2. No build errors
cd packages/sentinel-viz && npm run build 2>&1 | tail -5
# Expected: "built in X.Xs" with no errors
# NOT acceptable: "error during build", red text

# 3. Cesium token is valid (check browser console after opening localhost:3000)
# Expected: Globe renders the 3D tiles without a "Cesium Ion token" error banner
# If you see a pink/red Cesium attribution error: VITE_CESIUM_TOKEN is wrong

# 4. OpenSky layer has aircraft (browser console)
# Open localhost:3000, open DevTools console, run:
# window.layerManager._layers.get('aircraft')._byId.size
# Expected: integer > 0 within 30 seconds of page load
# Note: may be 0 if OpenSky API is rate-limiting — try again after 60s

# 5. Satellite layer loads
# Browser console: window.layerManager._layers.get('satellite')._sats.length
# Expected: > 1000 (CelesTrak active satellites feed)
```

**M2 is NOT complete if:**
- Build fails with errors
- Globe shows a solid grey sphere (3D tiles not loading)
- Cesium Ion error banner appears (invalid token)
- Aircraft count stays at 0 for more than 5 minutes

---

## M3 — RF → Globe (the critical integration milestone)

**What this milestone means:** Aircraft on the globe are sourced from the
local dump1090-rs RTL-SDR receiver, NOT from OpenSky or any internet API.
This is the hardest milestone to fake — it requires physical hardware.

### Checks

```bash
# 1. Confirm OpenSky is NOT being called
# Open browser DevTools → Network tab → filter for "opensky"
# Load the globe at localhost:3000 or localhost:8080
# Expected: ZERO requests to opensky-network.org
# If you see OpenSky requests: the fallback is still active

# 2. Confirm sentinel-rf WS is the data source
# Browser DevTools → Network → WS tab
# Expected: one WebSocket connection to ws://localhost:8080/ws/stream
# Messages should be arriving regularly

# 3. Confirm events have source="rf" not source="opensky"
redis-cli XRANGE sentinel:events - + COUNT 5
# In the JSON output, look for "source": "rf"
# NOT acceptable: "source": "opensky" or any other source for aircraft events

# 4. Confirm aircraft count matches dump1090 (within ~10%)
DUMP=$(curl -s http://localhost:8080/data/aircraft.json | \
  python3 -c "import sys,json; print(len(json.load(sys.stdin)['aircraft']))")
# Then in browser console:
# CESIUM = window.layerManager._layers.get('aircraft')._byId.size
echo "dump1090 aircraft: $DUMP"
echo "Compare to Cesium entity count in browser console"
# Expected: counts within ~10% of each other

# 5. Move test: verify a specific aircraft appears on globe
# Pick an aircraft from dump1090 feed:
curl -s http://localhost:8080/data/aircraft.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
ac = [a for a in d['aircraft'] if a.get('flight')][:3]
for a in ac: print(f\"{a['hex'].upper()}: {a.get('flight','').strip()} at {a.get('lat')},{a.get('lon')}\")
"
# Then verify that ICAO hex appears in browser:
# window.layerManager._layers.get('aircraft')._byId.has('ICAO-ABCDEF')
# Expected: true
```

**M3 is NOT complete if:**
- Any OpenSky API request is visible in the Network tab
- Aircraft source in Redis is not `"rf"`
- Aircraft count in Cesium doesn't roughly match dump1090

---

## M4 — OSINT profile

**What this milestone means:** Given a real Strava user ID or a geographic
coordinate with known WiFi networks, sentinel-osint produces a ProfileRecord
in the database with at least two sources contributing to it.

### Checks

```bash
# 1. OSINT health
curl -s http://localhost:5001/api/v1/health | python3 -m json.tool
# Expected: "status": "ok", collectors list shows available/unavailable status

# 2. Trigger enrichment for a test area
JOB=$(curl -s -X POST \
  "http://localhost:5001/api/v1/enrich?lat=51.5074&lon=-0.1278&radius_m=1000" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB"

# 3. Wait for job completion (up to 120 seconds)
for i in $(seq 1 24); do
  STATUS=$(curl -s "http://localhost:5001/api/v1/jobs/$JOB" | \
    python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "complete" ] && break
  sleep 5
done
# Expected: "complete" within 120 seconds

# 4. Raw records were collected
psql $SENTINEL_POSTGRES_URL -c \
  "SELECT source, COUNT(*) FROM raw_records GROUP BY source ORDER BY count DESC;"
# Expected: at least one source has count > 0

# 5. At least one profile was created
psql $SENTINEL_POSTGRES_URL -c \
  "SELECT entity_id, sources, confidence, lat, lon FROM profiles LIMIT 5;"
# Expected: at least one row with sources containing 2+ entries

# 6. Profile is accessible via API
curl -s "http://localhost:5001/api/v1/profiles?lat=51.5074&lon=-0.1278&radius_m=2000" | \
  python3 -c "import sys,json; p=json.load(sys.stdin); print(f'{len(p)} profiles found')"
# Expected: integer > 0
```

**M4 is NOT complete if:**
- No raw records in the database after enrichment
- Profile has only one source (linking not working)
- API returns empty list for the enriched area
- Job stays in "running" for more than 5 minutes (collector hanging)

---

## M5 — Unified wrapper

**What this milestone means:** sentinel-core is serving all modules behind
a single origin at localhost:8080. Auth is working. Health dashboard is green.

### Checks

```bash
# 1. sentinel-core serves the viz frontend
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/
# Expected: 200

# 2. Auth: unauthenticated request is rejected
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/rf/api/v1/health
# Expected: 401

# 3. Auth: obtain token and use it
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
echo "Token obtained: ${TOKEN:0:20}..."

# 4. Authenticated request proxied to RF module
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/rf/api/v1/health | python3 -m json.tool
# Expected: RF health JSON (not 401, not 502)

# 5. Unified health aggregator
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/health | python3 -m json.tool
# Expected: JSON with "modules" containing rf, osint, ai
# All available modules should show "status": "ok"

# 6. WebSocket stream available
# Browser console: new WebSocket('ws://localhost:8080/ws/stream')
# Expected: WebSocket opens (readyState 1) within 2 seconds
```

**M5 is NOT complete if:**
- Unauthenticated requests succeed (auth not enforced)
- Proxy returns 502 for any module (module unreachable)
- Health aggregator shows any module as "unreachable" that should be running
- WebSocket connection is refused or immediately closed

---

## M6 — Profile pins on globe

**What this milestone means:** OSINT profile coordinates appear as clickable
markers on the 3D globe. Clicking a marker shows the profile data panel.

### Checks

```bash
# 1. ProfileLayer is registered in LayerManager
# Browser console: window.layerManager._layers.has('profile')
# Expected: true

# 2. Profiles are fetched from OSINT API
# Browser DevTools → Network → filter for "profiles"
# Expected: GET request to /api/osint/api/v1/profiles with lat/lon params

# 3. Profile markers are present on globe
# Browser console: window.layerManager._layers.get('profile')._byId.size
# Expected: integer > 0 (if M4 completed successfully with profiles in DB)

# 4. Clicking a marker opens the info panel
# Click a profile marker on the globe
# Expected: InfoPanel appears with at minimum: entity_id, sources list, confidence score
# NOT acceptable: click does nothing, or panel shows "undefined" fields

# 5. Verify profile lat/lon matches globe pin location
# Browser console: window.layerManager._layers.get('profile')._byId.values().next().value
# Note the lat/lon from the entity
# Then zoom globe to that location and verify the pin is there
```

**M6 is NOT complete if:**
- No profile markers visible on globe with profiles in the database
- Clicking a marker does nothing
- Info panel shows undefined/null fields

---

## M7 — AI alert fires

**What this milestone means:** A WiFi BSSID detected by the SDR matches a
BSSID in an OSINT profile. sentinel-ai fires a high-confidence alert. The
alert appears in the globe's alert drawer within 60 seconds.

### Checks

```bash
# 1. Set up a controlled test: insert a profile with a known BSSID
python3 - << 'EOF'
import asyncio
from sentinel_osint.models.profile import ProfileRecord
from sentinel_osint.db import AsyncSessionLocal
import uuid

async def insert_test_profile():
    async with AsyncSessionLocal() as db:
        p = ProfileRecord(
            entity_id="test-alert-profile",
            lat=51.5074, lon=-0.1278,
            confidence=0.9,
            sources=["wigle"],
            identifiers={"bssid": "DE:AD:BE:EF:00:01", "ssid": "TestNet_Alert"},
            attributes={},
            raw_ids=[]
        )
        db.add(p)
        await db.commit()
        print("Test profile inserted")

asyncio.run(insert_test_profile())
EOF

# 2. Publish a matching WiFi event to the bus
python3 - << 'EOF'
import asyncio
from sentinel_common.bus import BusPublisher
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

async def publish_wifi():
    pub = BusPublisher()
    for _ in range(3):  # Publish multiple to exceed MIN_EVENTS_TO_CORRELATE
        await pub.publish(EventEnvelope(
            source="rf", kind=EventKind.WIFI,
            lat=51.5075, lon=-0.1279,
            entity_id="WIFI-DE:AD:BE:EF:00:01",
            payload={"bssid": "DE:AD:BE:EF:00:01", "ssid": "TestNet_Alert", "power_dbm": "-45"}
        ))
    await pub.close()
    print("WiFi events published")

asyncio.run(publish_wifi())
EOF

# 3. Wait for the correlation window to flush (up to 35 seconds)
echo "Waiting for correlation window (30s)..."
sleep 35

# 4. Check alerts were created
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/ai/api/v1/alerts | python3 -c "
import sys, json
alerts = json.load(sys.stdin)
print(f'Alerts: {len(alerts)}')
for a in alerts:
    print(f'  - confidence: {a[\"confidence\"]:.2f} | {a[\"summary\"]}')
"
# Expected: at least one alert with confidence >= 0.6
# Summary should reference the BSSID or profile match

# 5. Alert appears in browser drawer
# Open localhost:8080, look at the alert drawer (right panel)
# Expected: alert visible with confidence badge, summary text, and "Fly to" button
```

**M7 is NOT complete if:**
- No alerts in the database after the test sequence
- Alert confidence is below 0.6
- Alert appears in DB but not in the globe drawer
- `ANTHROPIC_API_KEY` error in sentinel-ai logs

---

## M8 — Full stack demo

**What this milestone means:** All layers running simultaneously. Live
aircraft and satellites from real sources. Profile overlays from OSINT.
AI alerts active. All shader modes work. All this with zero errors in logs.

### Checks

```bash
# 1. All services healthy
for svc in sentinel-rf sentinel-osint sentinel-ai sentinel-core; do
  STATUS=$(docker compose ps $svc --format json | python3 -c \
    "import sys,json; print(json.load(sys.stdin)[0]['State'])" 2>/dev/null)
  echo "$svc: $STATUS"
done
# Expected: all "running"

# 2. Zero ERROR logs in the last 5 minutes
for svc in sentinel-rf sentinel-osint sentinel-ai sentinel-core; do
  ERRORS=$(docker compose logs $svc --since 5m 2>&1 | grep -c "ERROR" || true)
  echo "$svc errors: $ERRORS"
done
# Expected: all 0

# 3. Event throughput is healthy
redis-cli XLEN sentinel:events
sleep 30
redis-cli XLEN sentinel:events
# Expected: second count is higher (events are flowing)

# 4. Globe performance
# Browser console: viewer.scene.lastRenderTime
# Rapidly pan/zoom the globe, then check:
# window.performance.getEntriesByType('paint')
# Expected: no jank, smooth camera movement

# 5. Shader modes
# Press 1, 2, 3, 4 on the keyboard
# Expected: globe switches between Standard, NVG, FLIR, CRT modes
# No console errors on each switch

# 6. Screenshot for documentation
# Take a screenshot of the globe showing aircraft + profile pins + one alert
# Save to docs/screenshots/m8-full-stack.png
```

**M8 is NOT complete if:**
- Any service has ERROR log entries in the last 5 minutes
- Events are not flowing (stream length not increasing)
- Any shader mode crashes or produces console errors
- Globe shows <10 aircraft in a populated area
