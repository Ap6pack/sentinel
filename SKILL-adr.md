# SKILL: Architecture Decision Records (ADRs)

## Purpose
This file explains *why* key architectural decisions were made. Read this
before proposing to change a technology, refactor a pattern, or add a
dependency that seems to contradict the current design. If you think a
decision here is wrong, open a discussion — do not silently refactor around it.

---

## How to read this file

Each ADR has: the decision, the alternatives considered, the reason the
alternatives were rejected, and the consequences to be aware of. If you find
yourself wanting to change a decision, that is a new ADR — add it at the
bottom with the date and reasoning.

---

## ADR-001 — Redis Streams as the event bus (not Kafka, not RabbitMQ)

**Decision:** Use Redis Streams (`XADD`/`XREADGROUP`) as the single event bus
across all modules.

**Alternatives rejected:**

- *Kafka* — operationally heavyweight for a single-operator deployment. Requires
  ZooKeeper or KRaft, JVM, separate broker processes. Total overkill for
  <50k events/hour. Can be introduced in a future multi-node production
  deployment without changing the `BusPublisher`/`BusConsumer` interface.

- *RabbitMQ* — AMQP adds complexity without benefit at this scale. No
  native stream/replay semantics (requires plugins).

- *asyncio Queue in-process* — works perfectly for a single process but
  breaks the moment any module runs as a separate Docker container.

- *Direct HTTP webhooks between modules* — violates the loose-coupling
  principle. Every producer would need to know every consumer's URL.

**Consequences:**
- Redis is a required dependency even for the basic Docker profile
- Stream grows until trimmed — `MAX_LEN=50_000` keeps it bounded
- In-memory fakeredis can substitute in tests and development without Docker
- If Redis goes down, events are lost for that period (no durability guarantee
  beyond `appendonly yes` persistence). This is acceptable for sensor data.

---

## ADR-002 — Flask-SocketIO for sentinel-rf (not FastAPI)

**Decision:** sentinel-rf uses Flask-SocketIO (inherited from iNTERCEPT),
not FastAPI.

**Alternatives rejected:**

- *Migrate to FastAPI* — iNTERCEPT's Flask-SocketIO code is battle-tested
  against real SDR hardware. Rewriting it introduces risk with zero user-
  visible benefit. The Flask-SocketIO standalone UI (at :5050) is valuable
  for debugging without the full stack running.

**Consequences:**
- sentinel-rf uses `gevent` for async, not `asyncio`. Do not mix them.
  Any code in sentinel-rf that needs `asyncio` must be isolated in a
  separate thread with `asyncio.run()`.
- The BusPublisher in sentinel-rf uses `redis-py` synchronous client
  wrapped in a thread, not `redis.asyncio`. This is the one exception
  to the "asyncio throughout" rule.
- sentinel-core's reverse proxy handles the impedance mismatch between
  Flask-SocketIO and FastAPI cleanly.

---

## ADR-003 — NetworkX for identity graph (not Neo4j)

**Decision:** Use NetworkX (in-memory Python graph library) for the identity
linker, with Neo4j as an opt-in production upgrade path.

**Alternatives rejected:**

- *Neo4j from the start* — requires a separate Docker service, Java runtime,
  and Cypher query language. For a v1.0 single-operator deployment processing
  hundreds (not millions) of profiles, NetworkX is fast enough and requires
  zero infrastructure.

- *Postgres with adjacency list table* — workable but graph traversal queries
  (find all connected components) are verbose and slow in SQL.

**Consequences:**
- The identity graph is lost on restart in development (no persistence by default)
- For production deployments with the `history` profile, the graph should
  be serialised to Postgres on each update using `networkx.node_link_data()`
  and reloaded on startup
- NetworkX connected_components() is O(V+E) — fine for <100k nodes
- If the profile count grows beyond ~500k nodes, migrate to Neo4j. The
  `IdentityGraph` class interface (`.add_record()`, `.link()`, `.profiles()`)
  is designed to be swapped without changing callers.

---

## ADR-004 — CesiumJS over deck.gl + Mapbox

**Decision:** Use CesiumJS as the 3D globe engine.

**Alternatives rejected:**

- *deck.gl over Mapbox* — excellent for 2D + slight tilt views, powerful
  layer system. However: no native 3D tile support at the time of this
  decision, no built-in satellite orbit propagation, no CZML support, and
  the camera model is 2D-first which makes the Palantir-style "spin the
  globe" UX awkward.

- *Three.js with custom globe* — full control but requires building
  tile loading, camera controls, label rendering, and orbit math from scratch.
  Months of work to reach feature parity with CesiumJS.

- *Google Earth Web* — not embeddable as a library.

**Consequences:**
- CesiumJS bundle is ~3MB gzipped — larger than deck.gl
- Requires a Cesium Ion access token for Google 3D Tiles (free tier available)
- `requestRenderMode: true` is mandatory — CesiumJS without it renders at
  60fps permanently and will drain laptop batteries
- CesiumJS uses a right-handed coordinate system (ECEF) — all position math
  must use `Cesium.Cartesian3.fromDegrees(lon, lat, alt)` not (lat, lon)

---

## ADR-005 — Vanilla JS for sentinel-viz (not React/Vue)

**Decision:** sentinel-viz is vanilla ES modules with no UI framework.

**Alternatives rejected:**

- *React* — the globe is a single imperative canvas, not a component tree.
  React's reconciliation model fights against CesiumJS's entity mutation
  pattern. Every aircraft position update would trigger a re-render check
  against a virtual DOM that has no knowledge of the Cesium scene.

- *Vue* — same argument as React. The reactive data model is a poor fit for
  a scene with 2,000+ entities updating every second.

**Consequences:**
- No component library — all UI is hand-rolled HTML/CSS
- No state management library — state lives in class instances (`LayerManager`,
  `BusClient`, `PostFxManager`)
- No TypeScript — JSDoc provides type hints; full TS migration is a future ADR
- Testing is `vitest` with `jsdom` — not a full browser environment, so
  CesiumJS rendering cannot be unit tested (only logic can be tested)

---

## ADR-006 — JWT with shared secret (not OAuth2 / per-module keys)

**Decision:** All modules share a single JWT secret (`SENTINEL_JWT_SECRET`)
and validate tokens locally without calling sentinel-core.

**Alternatives rejected:**

- *OAuth2 with PKCE* — correct for multi-user, multi-tenant deployments.
  Overkill for a single-operator v1.0. Planned for v2.0.

- *Per-module API keys* — would require each module to maintain a key store
  and every cross-module call to carry the right key. Adds surface area with
  no security benefit in a single-operator deployment where all modules run
  on the same host.

- *mTLS between modules* — operationally complex, certificate rotation is
  painful in development.

**Consequences:**
- Anyone who obtains `SENTINEL_JWT_SECRET` has full access to all modules
- The secret must be rotated by restarting all services simultaneously
- This is a known limitation — the security model assumes the host is trusted
- For internet-exposed deployments, put nginx with client certificates in
  front of sentinel-core and never expose module ports directly

---

## ADR-007 — claude-sonnet-4-6 for correlation (not a local model)

**Decision:** Use the Anthropic Claude API (`claude-sonnet-4-6`) for
correlation reasoning, not a locally-hosted model.

**Alternatives rejected:**

- *Local LLM (Ollama/llama.cpp)* — correlation reasoning requires multi-source
  synthesis with 1-2k token context. Local models capable of this quality
  require 16GB+ VRAM. A Raspberry Pi deployment cannot run them. The operator
  experience (reasoning quality, latency) is significantly worse.

- *Rule-based correlation (no LLM)* — BSSID and username exact matches can
  be rule-based. But the value of `sentinel-ai` is synthesising ambiguous
  multi-source observations into actionable alerts. That requires language
  model reasoning.

- *GPT-4 / Gemini* — viable alternatives. The `correlator.py` interface
  (`correlate_batch()`) can be re-pointed at a different API by changing
  10 lines. Claude is chosen because it follows structured JSON output
  instructions more reliably than alternatives at the time of this decision.

**Consequences:**
- Requires `ANTHROPIC_API_KEY` — sentinel-ai will not start without it
- API calls cost real money — rate limit with `SENTINEL_AI_MAX_CALLS_PER_HOUR`
- Correlation requires internet connectivity — sentinel-ai is the only
  module with this requirement
- Latency: ~2-8 seconds per correlation call — acceptable for alert generation,
  not acceptable for real-time event processing (which is why we batch)

---

## ADR-008 — Modular packages over a monolith

**Decision:** Five separate Python packages (`sentinel-common`, `sentinel-core`,
`sentinel-rf`, `sentinel-osint`, `sentinel-ai`) rather than one application.

**Alternatives rejected:**

- *Single FastAPI application with module folders* — faster to start, but
  makes it impossible to deploy only the RF layer on a Raspberry Pi without
  carrying all OSINT and AI dependencies. Also makes it impossible to run
  multiple RF nodes without running a full stack instance.

**Consequences:**
- `sentinel-common` version must be pinned identically across all packages
- Changes to the event envelope require coordinated package updates
- Local development requires installing all packages in editable mode
  (`pip install -e packages/sentinel-common packages/sentinel-rf ...`)
- Docker images are per-module — build times are longer but images are smaller

---

## Adding a new ADR

When a significant architectural decision is made, add it here:

```
## ADR-00N — [Short title]

**Decision:** [What was decided]

**Alternatives rejected:**
- *Option A* — [Why rejected]
- *Option B* — [Why rejected]

**Consequences:**
- [What this means for developers]
- [Known limitations]
- [Future migration path if needed]
```

Date and author are tracked in git blame — no need to include them in the text.
