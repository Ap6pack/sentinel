# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.5.0] - 2026-04-05

### Added
- **sentinel-core** OSINT proxy integration
  - Authenticated reverse proxy routes `/api/osint/*` to sentinel-osint on :5001
  - sentinel-osint added to health aggregator polling
  - 3 new tests confirming auth enforcement and proxy routing for OSINT endpoints

## [0.4.0] - 2026-04-05

### Added
- **sentinel-osint** package — OSINT collection and identity linking
  - SQLAlchemy 2.0 async models: `ProfileRecord`, `RawRecord` with `Mapped[]` type hints
  - Alembic migration setup with sync psycopg2 URL conversion for async engines
  - Async session factory (`AsyncSessionLocal`) with `expire_on_commit=False`
  - `BaseCollector` ABC with sliding-window rate limiter
  - Five collectors: WiGLE (WiFi networks), Fitness (Strava routes with home-coord inference), Reviews (Google Places), Property (county assessor records), Username (cross-platform search)
  - Identity linker with NetworkX graph and five link trigger rules: BSSID match (0.95), username match (0.90), spatial home cluster (0.80), name+city match (0.60), photo hash match (0.95)
  - `build_profile()` merging raw records into a single `ProfileRecord` with source-priority ordering
  - `publish_profile()` and `publish_profile_link()` event bus publishers
  - FastAPI app with `/api/v1/health` and `/api/v1/profiles` (bbox query) endpoints
  - `OsintSettings` via pydantic-settings reading `SENTINEL_OSINT_*` env vars
  - 44 unit tests (SQLite in-memory, pytest-httpx for HTTP mocks)

## [0.3.0] - 2026-04-05

Tag: `m3-rf-globe`

### Added
- **sentinel-core** package — FastAPI platform wrapper
  - JWT authentication (issue, verify, middleware)
  - Bus bridge: Redis Streams XREAD to WebSocket fan-out with per-client filtering
  - Reverse proxy routing `/api/{rf,osint,ai}/*` to module backends
  - Health aggregator polling all module `/api/v1/health` endpoints
  - CORS middleware, login endpoint, WebSocket `/ws/stream`
- End-to-end integration: mock RF decoder publishes to Redis, bridge forwards to browser via WebSocket
- 18 unit tests for sentinel-core (auth, bridge filtering, app routes, health)

## [0.2.0] - 2026-04-05

### Added
- **sentinel-viz** package — CesiumJS 3D globe visualisation
  - Globe with Google Photorealistic 3D Tiles (asset 2275207), `requestRenderMode: true`
  - AircraftLayer (cyan points, 2000 cap, 60s prune, `NearFarScalar` + `DistanceDisplayCondition`)
  - VesselLayer (yellow points, 2000 cap, 120s prune)
  - SatelliteLayer (CelesTrak TLE fetch, SGP4 propagation via satellite.js, 500 cap)
  - AlertLayer (red pins for AI-generated alerts)
  - LayerManager with event routing and visibility toggles
  - BusClient WebSocket consumer with auto-reconnect and exponential backoff
  - PostFxManager with NVG, FLIR, and CRT full-screen GLSL shaders
  - ControlPanel UI (layer checkboxes, shader mode buttons)
  - CameraPresets bound to Q/W/E keys (London, Heathrow, English Channel)
  - InfoPanel click-on-entity popup
  - Mock event feed for development (`VITE_NO_MOCK=1` to disable)
  - Vite build with `vite-plugin-cesium`

## [0.1.0] - 2026-04-05

### Added
- **sentinel-common** package — shared contracts and event bus
  - `EventEnvelope` Pydantic model with coordinate validation and Redis serialisation
  - `EventKind` StrEnum (13 kinds: aircraft, vessel, wifi, bluetooth, pager, aprs, weather_sat, profile, profile_link, alert, correlation, heartbeat, health)
  - `BusPublisher` (Redis Streams XADD) and `BusConsumer` (XREADGROUP with consumer groups and kind filtering)
  - `SentinelSettings` via pydantic-settings reading `SENTINEL_*` env vars
  - `haversine_m()` and `bbox_contains()` geo helpers
  - 16 unit tests
- **sentinel-rf** package — RF/SDR signal intelligence layer
  - `BaseDecoder` ABC with subprocess lifecycle management and exponential backoff restart
  - `ADSBDecoder` poll-based decoder with live mode (HTTP poll of dump1090-rs) and mock replay mode
  - `RFPublisher` with GPS coordinate enrichment for coord-less events
  - Flask-SocketIO app with `/api/v1/health` and `/api/v1/decoders` endpoints
  - Mock mode (`SENTINEL_RF_MOCK=true`) replays `tests/fixtures/aircraft_sample.json`
  - 17 unit tests
- Docker Compose configuration with profiles (basic, full, history, mock)
- `.gitignore`, `.env.example` files, copyright headers

[Unreleased]: https://github.com/Ap6pack/sentinel/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/Ap6pack/sentinel/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Ap6pack/sentinel/compare/m3-rf-globe...v0.4.0
[0.3.0]: https://github.com/Ap6pack/sentinel/releases/tag/m3-rf-globe
[0.2.0]: https://github.com/Ap6pack/sentinel/releases/tag/m3-rf-globe
[0.1.0]: https://github.com/Ap6pack/sentinel/releases/tag/m3-rf-globe
