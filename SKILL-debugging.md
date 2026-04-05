# SKILL: Debugging — decision trees for every pipeline stage

## Purpose
When something is broken, work through the relevant decision tree top to
bottom. Do not skip steps. Most SENTINEL bugs are integration bugs — the
component you are looking at is fine, and the problem is in the step before
it. The trees are ordered to surface that as fast as possible.

---

## Tree 1 — No aircraft on the globe

```
Aircraft not appearing on globe
│
├── Is sentinel-rf running?
│   curl http://localhost:5050/api/v1/health
│   ├── Connection refused → docker compose ps sentinel-rf
│   │   ├── Exited → docker compose logs sentinel-rf --tail 50
│   │   │   ├── "no RTL-SDR device found" → Check USB: lsusb | grep RTL
│   │   │   ├── "Address already in use :5050" → kill orphan: lsof -i :5050
│   │   │   └── Python traceback → fix the import error shown
│   │   └── Running but health fails → check dump1090-rs subprocess
│   └── OK → continue ↓
│
├── Are events reaching Redis?
│   redis-cli XLEN sentinel:events
│   ├── 0 → RF is running but not publishing
│   │   redis-cli MONITOR (watch for XADD calls)
│   │   ├── No XADD seen → check publisher.py GPS enrichment blocking
│   │   └── XADD seen but count stays 0 → wrong stream name (check STREAM_NAME)
│   └── > 0 → continue ↓
│
├── Are aircraft events specifically present?
│   redis-cli XRANGE sentinel:events - + COUNT 20 | grep aircraft
│   ├── No aircraft kind → dump1090-rs not decoding
│   │   curl http://localhost:8080/data/aircraft.json
│   │   ├── Connection refused → dump1090-rs subprocess not started
│   │   │   Check: ps aux | grep dump1090
│   │   ├── {"aircraft": []} → no planes in range OR wrong device index
│   │   │   Check: SENTINEL_ADSB_DEVICE_INDEX in .env
│   │   └── Aircraft present → polling loop in adsb.py not running
│   └── Aircraft events present → continue ↓
│
├── Is sentinel-core bridge running?
│   curl http://localhost:8080/api/v1/health
│   └── Check bridge loop: docker compose logs sentinel-core | grep bridge
│
├── Is the WebSocket connected in the browser?
│   DevTools → Network → WS → look for /ws/stream connection
│   ├── No connection → check VITE_WS_URL in sentinel-viz .env.local
│   ├── Connection then immediate close → JWT auth failure
│   │   Check: browser console for 401 errors
│   └── Connected → continue ↓
│
├── Is the aircraft layer enabled?
│   Browser console: window.layerManager._layers.get('aircraft').enabled
│   ├── false → layer toggle is off — enable it in the control panel
│   └── true → continue ↓
│
└── Is the filter spec excluding aircraft?
    Browser console: window.busClient._filterSpec
    └── If kinds array doesn't include 'aircraft' → update filter in main.js
```

---

## Tree 2 — OSINT profile not found / enrichment not working

```
Profile missing or enrichment returns empty
│
├── Was enrich triggered?
│   POST http://localhost:5001/api/v1/enrich?lat=X&lon=Y&radius_m=500
│   └── Check response for job_id, then GET /api/v1/jobs/{job_id}
│
├── Which collector is failing?
│   docker compose logs sentinel-osint --tail 100 | grep WARNING
│   ├── "[wigle] 429" → Rate limited. Wait 60s and retry.
│   ├── "[wigle] missing API key" → Set SENTINEL_WIGLE_API_KEY in .env
│   ├── "[strava] 401" → Token expired. Re-authenticate.
│   └── "[collector] timeout" → External service unreachable
│
├── Are raw records being stored?
│   In psql: SELECT source, COUNT(*) FROM raw_records GROUP BY source;
│   ├── Empty → collectors ran but yielded nothing
│   │   Check bounding box: is the lat/lon within the collector's search area?
│   └── Records present but no profile → linker not running
│
├── Is the identity linker finding links?
│   docker compose logs sentinel-osint | grep "link\|graph\|component"
│   ├── "0 links found" → records don't share identifiers
│   │   This is expected if the target has no cross-platform presence
│   └── Links found but no profile built → check builder.py threshold
│
└── Is the profile visible in the API?
    curl "http://localhost:5001/api/v1/profiles?lat=X&lon=Y&radius_m=1000"
    ├── [] → Profile lat/lon outside search radius
    │   Check: profile.lat/lon in DB vs search coordinates
    └── Profile present → globe overlay not fetching
        Check: sentinel-viz ProfileLayer fetch interval and URL
```

---

## Tree 3 — AI alert not firing

```
Expected alert not appearing in globe drawer
│
├── Is sentinel-ai running?
│   curl http://localhost:5002/api/v1/health
│   └── Check: ANTHROPIC_API_KEY set in .env
│
├── Is the event window accumulating events?
│   docker compose logs sentinel-ai | grep "window\|batch\|flush"
│   ├── No flush logs → consumer not receiving events
│   │   Check BusConsumer group: redis-cli XINFO GROUPS sentinel:events
│   └── Flushing but no Claude call → batch size below MIN_EVENTS_TO_CORRELATE
│
├── Is the spatial join finding profiles?
│   docker compose logs sentinel-ai | grep "nearby_profiles\|spatial"
│   ├── "0 profiles found" → No OSINT profiles near the RF events
│   │   This is correct behaviour — no alert should fire without a profile match
│   └── Profiles found → continue ↓
│
├── Did the Claude API call succeed?
│   docker compose logs sentinel-ai | grep "correlator\|claude\|anthropic"
│   ├── "rate limit reached" → Increase SENTINEL_AI_MAX_CALLS_PER_HOUR
│   ├── "authentication_error" → Invalid ANTHROPIC_API_KEY
│   ├── "Claude response was not valid JSON" → Prompt produced non-JSON output
│   │   Check: prompts/correlate.txt — is the JSON instruction still intact?
│   └── No logs → correlator.py exception being swallowed
│       Add temporary: logger.exception("correlator error") in except block
│
├── Did Claude decide no alert was warranted?
│   The most common case. Check the reasoning:
│   docker compose logs sentinel-ai | grep "alert_warranted"
│   └── "false" → confidence below 0.6 threshold
│       This is correct — not every RF+profile match warrants an alert
│
└── Alert created but not visible in drawer?
    curl http://localhost:5002/api/v1/alerts
    ├── Alert present → not published to bus
    │   Check publisher call in correlator.py after alert persistence
    └── Alert absent → DB write failed
        Check: alembic upgrade head has been run for sentinel-ai
```

---

## Tree 4 — Redis connection errors

```
"Connection refused" or "Redis unavailable" in any module
│
├── Is Redis running?
│   docker compose ps redis
│   ├── Not running → docker compose up redis -d
│   └── Running → continue ↓
│
├── Is the URL correct?
│   echo $SENTINEL_REDIS_URL
│   ├── Empty → SENTINEL_REDIS_URL not set in .env
│   ├── redis://localhost:6379 → correct for local dev
│   └── redis://redis:6379 → correct inside Docker network
│       (modules inside Docker must use service name, not localhost)
│
├── Can you ping Redis?
│   redis-cli -u $SENTINEL_REDIS_URL ping
│   ├── PONG → Redis is up, connection string is wrong in the module
│   └── Error → Redis port not exposed or firewall blocking
│
└── Is the stream too large causing memory pressure?
    redis-cli MEMORY USAGE sentinel:events
    └── If > 100MB: redis-cli XTRIM sentinel:events MAXLEN 10000
```

---

## Tree 5 — WebSocket disconnects repeatedly

```
Globe WebSocket keeps disconnecting and reconnecting
│
├── Check reconnect interval in browser console
│   Look for "[bus] closed, reconnecting in Xms"
│   ├── X doubling rapidly → exponential backoff triggered by server closes
│   └── Constant interval → client-side timeout
│
├── Is sentinel-core bridge crashing?
│   docker compose logs sentinel-core | grep "bridge\|ERROR\|exception"
│   └── RuntimeError: "event loop closed" → bridge task not cancelled cleanly
│       Fix: ensure broadcast_loop task is cancelled in shutdown hook
│
├── Is the JWT expiring?
│   Decode the JWT: python3 -c "import jwt,os; print(jwt.decode(TOKEN, options={'verify_signature':False}))"
│   ├── exp in the past → token expired, re-login
│   └── exp in future → JWT is fine, check other causes
│
└── Is Redis producing events faster than the bridge can forward?
    redis-cli XINFO GROUPS sentinel:events
    Look for "pel-count" (pending entries) growing rapidly
    └── Growing → bridge is behind; check for slow WebSocket clients
        Mitigation: reduce MAX_LEN on the stream or add client-side buffering
```

---

## Tree 6 — Database migration failures

```
"relation does not exist" or migration error on startup
│
├── Has alembic upgrade head been run?
│   alembic current
│   ├── "No current revision" → alembic upgrade head
│   └── Shows a revision → continue ↓
│
├── Is the migration targeting the right database?
│   alembic current --verbose | grep "database"
│   └── Check SENTINEL_POSTGRES_URL points to the correct DB
│
├── Did a previous migration fail halfway?
│   SELECT * FROM alembic_version;
│   └── If version doesn't match head: alembic stamp head (only if you
│       manually fixed the schema) OR drop and recreate the DB in dev
│
└── Is there a column type mismatch?
    alembic check
    └── Shows differences → auto-generated migration was not applied
        Run: alembic revision --autogenerate -m "fix column type"
        Review, then: alembic upgrade head
```

---

## Quick diagnostic commands — bookmark these

```bash
# Full stack status
docker compose ps

# All module health at once
for port in 5050 5001 5002 8080; do
  echo -n "Port $port: "
  curl -s http://localhost:$port/api/v1/health | python3 -m json.tool | grep status
done

# Last 10 events on the bus
redis-cli XRANGE sentinel:events - + COUNT 10

# Event kinds distribution (last 1000 events)
redis-cli XRANGE sentinel:events - + COUNT 1000 | \
  grep '"kind"' | sort | uniq -c | sort -rn

# Active Redis consumer groups and lag
redis-cli XINFO GROUPS sentinel:events

# Postgres: quick table row counts
psql $SENTINEL_POSTGRES_URL -c \
  "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"

# CesiumJS entity count in browser console
Object.fromEntries(
  [...window.layerManager._layers.entries()]
    .map(([k,v]) => [k, v._byId?.size ?? 'n/a'])
)

# Check which SDR devices are attached
lsusb | grep -i "realtek\|rtl\|hackrf\|ubertooth"

# dump1090-rs raw aircraft feed
curl -s http://localhost:8080/data/aircraft.json | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d[\"aircraft\"])} aircraft')"
```

---

## Reading logs effectively

```bash
# Follow all module logs simultaneously with colour coding
docker compose logs -f --tail 20 sentinel-rf sentinel-osint sentinel-ai sentinel-core

# Filter for errors only
docker compose logs sentinel-rf 2>&1 | grep -E "ERROR|WARNING|Exception|Traceback"

# Find the first occurrence of a crash
docker compose logs sentinel-rf 2>&1 | grep -n "Traceback" | head -1
# Then: docker compose logs sentinel-rf 2>&1 | sed -n '${LINE},+20p'
```

Log levels to know:
- `DEBUG` — per-event processing; disabled in production (`SENTINEL_LOG_LEVEL=INFO`)
- `INFO` — subprocess starts, connection events, job completions
- `WARNING` — recoverable errors: rate limits, timeouts, decode failures
- `ERROR` — unexpected failures that need investigation
- `CRITICAL` — only used for unrecoverable startup failures

---

## When nothing in the trees helps

1. Enable `DEBUG` logging: set `SENTINEL_LOG_LEVEL=DEBUG` in `.env` and restart
2. Check `redis-cli MONITOR` — shows every Redis command in real time
3. Check `SENTINEL_RF_MOCK=true` — isolates hardware from software bugs
4. Wipe and restart: `docker compose down -v && docker compose --profile basic up -d`
   (this destroys Redis data — only do this in development)
5. Check git blame — `git log --oneline -10` — did a recent commit break something?
