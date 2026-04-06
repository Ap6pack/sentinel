# SENTINEL — Architecture

## Overview

SENTINEL is a modular open-source spatial intelligence platform. Three independent layers — physical RF signals, internet OSINT, and 3D visualisation — communicate through a shared event bus. A platform wrapper ties them together.

```
┌─────────────────────────────────────────────────────┐
│                  sentinel-core :8080                │
│  auth · reverse proxy · bus bridge · health         │
└──────────┬──────────────────────────────────────────┘
           │ WebSocket /ws/stream
           ▼
┌──────────────────────────────┐
│       Redis Streams          │  ← event bus (all modules publish here)
│    "sentinel:events"         │
└──────┬────────┬──────────────┘
       │        │
  ┌────▼──┐ ┌───▼────┐ ┌──────────┐
  │  RF   │ │ OSINT  │ │    AI    │
  │ :5050 │ │ :5001  │ │  :5002   │
  └───────┘ └────────┘ └──────────┘
       ↑ hardware           ↑ Claude API
       RTL-SDR         correlation
```

## Modules

### sentinel-common
Shared Pydantic models, event bus client, geo utilities, config. Every other module depends on this. Schema changes here require coordinated updates.

### sentinel-core
Platform wrapper. Provides JWT authentication shared across all modules, a reverse proxy routing `/rf`, `/osint`, `/ai` to their respective services, a Redis→WebSocket bridge for the viz frontend, and the Docker Compose orchestration.

### sentinel-rf
Layer 1. Flask-SocketIO app wrapping SDR CLI tools as async subprocesses. Decodes ADS-B, AIS, WiFi, Bluetooth, pagers, APRS, and weather satellites. Publishes normalised `EventEnvelope` objects to the bus. Works offline with no internet dependency. Set `SENTINEL_RF_MOCK=true` to replay fixture data without hardware.

### sentinel-osint
Layer 2. FastAPI app running async collector workers (Strava, WiGLE, Google Places, property records, username search). Stores raw records in Postgres, links them via a NetworkX identity graph, assembles `ProfileRecord` objects, and publishes `PROFILE` events to the bus.

### sentinel-viz
Layer 3. Vite + vanilla JS single-page application. CesiumJS globe with Google Photorealistic 3D Tiles. Consumes the bus via WebSocket. Data layers: aircraft, vessels, satellites (TLE), seismic, traffic simulation, OSINT profile overlays, AI alert pins. Shader modes: NVG, FLIR, CRT. Timeline scrubber for 4D replay (Phase 6).

### sentinel-ai
Correlation engine. Consumes bus events in 30-second batches, runs spatial joins against OSINT profiles, calls the Claude API for multi-source reasoning, and publishes `ALERT` events back to the bus.

## Event envelope

Every inter-module message uses this schema:

```json
{
  "id": "uuid4",
  "ts": "2024-01-01T14:32:00Z",
  "source": "rf | osint | ai | core",
  "kind": "aircraft | vessel | wifi | profile | alert | ...",
  "lat": 51.5074,
  "lon": -0.1278,
  "alt_m": 9800.0,
  "entity_id": "ICAO-3C4A6F",
  "payload": { ... }
}
```

All module-specific data goes in `payload`. Top-level fields are stable. See `SKILL-common.md` for version bump rules.

## Data flow example — aircraft on globe

```
RTL-SDR USB dongle
  → dump1090-rs (subprocess in sentinel-rf)
  → ADSBDecoder polls localhost:8080/data/aircraft.json
  → EventEnvelope(kind="aircraft", lat=51.5, lon=-0.1, ...)
  → BusPublisher.publish() → Redis XADD sentinel:events
  → BusBridge.broadcast_loop() reads Redis XREAD
  → WebSocket /ws/stream → browser
  → BusClient.onmessage() → LayerManager.route()
  → AircraftLayer.onEvent() → Cesium entity updated
  → viewer.scene.requestRender()
```

## Deployment profiles

| Profile | Services | Use case |
|---|---|---|
| `basic` | redis, core, rf, viz | Development, no OSINT or AI |
| `full` | all services | Complete platform |
| `history` | full + postgres | Production with persistence |
| `mock` | full, RF mock mode | CI and development without hardware |

```bash
docker compose --profile basic up -d
```

## Port map

| Port | Service |
|---|---|
| 8080 | sentinel-core (primary entry point) |
| 5050 | sentinel-rf (also accessible standalone) |
| 5001 | sentinel-osint |
| 5002 | sentinel-ai |
| 6379 | Redis |
| 5432 | Postgres (history/full profiles only) |
| 3000 | sentinel-viz dev server (local development) |
