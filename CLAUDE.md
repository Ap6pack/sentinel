# SKILL: SENTINEL — Agent orchestration & Claude Code conventions

## Purpose
This is the **meta-skill** — read it first, before any module-specific skill.
It defines how Claude Code agents should be orchestrated across the SENTINEL
monorepo, which skill file to load for each task, how to run tests, and the
conventions that apply platform-wide. Keep this file in the repo root as
`CLAUDE.md` so Claude Code loads it automatically on every session.

---

## Skill file index — load the right one before starting work

| Task area | Skill file to read first |
|---|---|
| Event bus, shared envelope schema, geo utils | `SKILL-common.md` |
| SDR decoders, subprocess management, RF pipeline | `SKILL-rf.md` |
| OSINT collectors, identity linker, profile model | `SKILL-osint.md` |
| CesiumJS globe, WebSocket consumer, shaders, layers | `SKILL-viz.md` |
| Auth, bus bridge, reverse proxy, Docker Compose | `SKILL-core.md` |
| Claude API, alert generation, correlation prompts | `SKILL-ai.md` |
| Any cross-cutting work (monorepo, CI, shared infra) | This file |

**Always read the relevant skill file before writing any code.**
Do not rely on general knowledge about these frameworks — the skill files
contain SENTINEL-specific conventions that override general best practices.

---

## Monorepo structure

```
sentinel/
├── CLAUDE.md                  ← you are here
├── SKILL-common.md
├── SKILL-rf.md
├── SKILL-osint.md
├── SKILL-viz.md
├── SKILL-core.md
├── SKILL-ai.md
├── packages/
│   ├── sentinel-common/
│   ├── sentinel-core/
│   ├── sentinel-rf/
│   ├── sentinel-osint/
│   ├── sentinel-viz/
│   └── sentinel-ai/
├── infra/
│   └── docker-compose.yml
├── docs/
└── tests/                     ← integration tests only (unit tests live in each package)
```

---

## Workspace setup commands

Run these once after cloning:

```bash
# Python packages — install all in editable mode into a shared venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e packages/sentinel-common
pip install -e packages/sentinel-core
pip install -e packages/sentinel-rf
pip install -e packages/sentinel-osint
pip install -e packages/sentinel-ai

# Frontend
cd packages/sentinel-viz && npm install && cd ../..

# Start backing services (Redis, Postgres)
docker compose -f infra/docker-compose.yml up redis postgres -d

# Verify common package
python -c "from sentinel_common.envelope import EventEnvelope; print('OK')"
```

---

## Running tests

```bash
# All Python unit tests
pytest packages/ -x -q

# Single package
pytest packages/sentinel-rf/ -x -q

# With coverage
pytest packages/ --cov=sentinel_common --cov=sentinel_rf --cov-report=term-missing

# Frontend
cd packages/sentinel-viz && npm test

# Integration tests (requires running Docker stack)
docker compose -f infra/docker-compose.yml --profile mock up -d
pytest tests/ -x -q -m integration
```

**Never skip failing tests.** If a test is flaky, fix it or mark it
`@pytest.mark.xfail(strict=True)` with a comment explaining why.

---

## Code style — Python

- Python 3.11+ only — use `match/case`, `tomllib`, PEP 695 type aliases freely
- `ruff` for linting and formatting — run `ruff check . --fix && ruff format .`
  before every commit
- Type hints on all function signatures — no bare `Any` without a comment
- Pydantic models for all data structures that cross module boundaries
- `asyncio` throughout — no synchronous I/O in the main event loop
- Logging via `logging.getLogger(__name__)` — never `print()` in production code
- Exception handling: catch specific exceptions, not bare `except:` — log at
  WARNING for recoverable errors, ERROR for unexpected ones

```python
# Good
logger = logging.getLogger(__name__)
try:
    result = await some_async_call()
except httpx.TimeoutException:
    logger.warning("Timeout calling %s", url)
    return None
except httpx.HTTPStatusError as e:
    logger.error("HTTP %d from %s", e.response.status_code, url)
    raise

# Bad
try:
    result = await some_async_call()
except:
    pass
```

---

## Code style — JavaScript (sentinel-viz)

- ESM modules throughout — no CommonJS `require()`
- `/** JSDoc */` on all exported functions and classes
- No framework (no React, no Vue) — vanilla JS + CesiumJS
- `eslint` + `prettier` — run `npm run lint && npm run format` before commit
- Named imports from CesiumJS — never `import * as Cesium` in production code
  (prevents tree-shaking); allowed only in exploratory scripts
- All async operations must handle errors — no unhandled promise rejections

---

## Environment variables — conventions

| Prefix | Scope | Example |
|---|---|---|
| `SENTINEL_` | Shared across all Python modules | `SENTINEL_REDIS_URL` |
| `SENTINEL_RF_` | sentinel-rf only | `SENTINEL_RF_MOCK` |
| `SENTINEL_OSINT_` | sentinel-osint only | `SENTINEL_OSINT_WIGLE_API_KEY` |
| `SENTINEL_AI_` | sentinel-ai only | `SENTINEL_AI_MAX_CALLS_PER_HOUR` |
| `VITE_` | sentinel-viz frontend (public) | `VITE_CESIUM_TOKEN` |

All env vars must have entries in:
1. `packages/{module}/.env.example` with a placeholder value
2. `infra/docker-compose.yml` under the relevant service's `environment:` block
3. The module's `config.py` Pydantic Settings model with a default or `...` (required)

Never add a new env var without updating all three.

---

## Git conventions

Branch naming:
- `feat/{module}/{short-description}` — new feature
- `fix/{module}/{short-description}` — bug fix
- `refactor/{module}/{short-description}` — refactoring
- `skill/{description}` — skill file updates

Commit messages follow Conventional Commits:
```
feat(rf): add AIS-catcher vessel decoder
fix(viz): prevent entity leak in AircraftLayer on rapid reconnect
refactor(common): extract haversine to geo.py
docs(skill-ai): clarify confidence threshold rules
```

Every PR must:
1. Pass all tests (`pytest packages/ -q` exits 0)
2. Pass linting (`ruff check packages/` exits 0)
3. Update the relevant SKILL file if the change affects conventions
4. Include at least one test for any new code path

---

## Inter-agent task handoff protocol

When running multiple Claude Code agents in parallel (one per module), use
this handoff format in your task description to avoid conflicting work:

```
TASK: [module name]
SKILL: [skill file name]
DEPENDS ON: [list of entity_ids or interfaces this task needs]
PRODUCES: [list of interfaces or entity_ids this task provides]
BLOCKING: [list of tasks that cannot start until this one completes]
STATUS: [not started | in progress | blocked | done]
```

Example:
```
TASK: sentinel-rf ADS-B decoder
SKILL: SKILL-rf.md
DEPENDS ON: sentinel-common EventEnvelope schema (must be finalised)
PRODUCES: EventKind.AIRCRAFT events on Redis Streams
BLOCKING: sentinel-viz AircraftLayer, sentinel-ai spatial join
STATUS: in progress
```

The bus contract (`SKILL-common.md`) and the event envelope schema must be
finalised before any other module agent starts writing code that produces or
consumes events.

---

## Debugging the event pipeline end-to-end

When something is not appearing on the globe, trace the pipeline in this order:

```bash
# 1. Is the RF decoder running and producing events?
curl http://localhost:5050/api/v1/health

# 2. Are events reaching Redis?
redis-cli XLEN sentinel:events
redis-cli XRANGE sentinel:events - + COUNT 5

# 3. Is sentinel-core bridge reading from Redis?
curl http://localhost:8080/api/v1/health

# 4. Is the WebSocket connection established from browser?
# Open browser DevTools → Network → WS tab → look for /ws/stream connection
# Send a test message to confirm round-trip

# 5. Is the layer enabled in LayerManager?
# Open browser console: window.layerManager._layers
```

---

## Performance baselines — know these numbers

| Metric | Target | Alert threshold |
|---|---|---|
| Redis Streams lag (consumer group) | < 100ms | > 1s |
| ADS-B poll interval | 1.0s | > 5s |
| Claude API correlation latency | < 8s | > 20s |
| CesiumJS frame time | < 16ms (60fps) | > 33ms (30fps) |
| Bus bridge WebSocket client count | ≤ 10 | > 50 (add load balancer) |
| OSINT profile enrichment job | < 60s | > 300s |

---

## What to do when you are stuck

1. **Re-read the relevant SKILL file** — the answer is usually there
2. **Check the event envelope** — most cross-module bugs are envelope field
   naming mismatches (`entity_id` vs `entityId` etc.)
3. **Check the Redis stream directly** with `redis-cli XRANGE` — confirms
   whether the problem is in the producer or the consumer
4. **Run with `SENTINEL_RF_MOCK=true`** — isolates whether the bug is in the
   SDR hardware path or the software pipeline
5. **Check Docker service logs** — `docker compose logs sentinel-rf --tail 50`
6. **Never silently swallow exceptions** — if you added a bare `except: pass`
   to "fix" a crash, that is the bug hiding the real bug

---

## Things never to do (platform-wide)

- Never import one sentinel module from another — use the bus or REST API
- Never commit secrets, tokens, or API keys — use `.env` files excluded by `.gitignore`
- Never use `time.sleep()` in async code — always `await asyncio.sleep()`
- Never use `threading` — everything is async; threads break the event loop
- Never disable tests with `pytest.mark.skip` without a GitHub issue number in the comment
- Never push directly to `main` — always use a PR
- Never set `SENTINEL_JWT_SECRET` to a known value in any committed file
- Never call the Claude API in a tight loop — always batch and rate-limit
