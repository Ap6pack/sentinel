# SENTINEL

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-51%20passing-brightgreen)]()
[![Status](https://img.shields.io/badge/status-active%20development-blue)]() 

> *Open-source spatial intelligence — RF signals, OSINT, and live geospatial
> data fused into a single operational picture.*

---

## Overview

SENTINEL combines three capabilities that have never existed together in an
open-source stack:

- **RF signal collection** — a $25 RTL-SDR dongle decodes ADS-B aircraft
  transponders, AIS vessel positions, 433MHz sensors, pager traffic, and weather
  satellite imagery directly from the air around you
- **OSINT correlation** — public fitness routes, review profiles, Wi-Fi
  geolocation, and property records are linked by an identity graph and pinned
  to coordinates
- **3D visualisation** — a CesiumJS globe with Google Photorealistic 3D Tiles,
  live tracks, satellite orbits, NVG/FLIR/CRT shader modes, and a timeline
  scrubber for 4D event replay

All three layers are independently deployable modules connected by a shared
event bus. An AI correlation engine generates alerts when signals match profiles.

No cloud dependency. No subscription. Self-hosted.

---

## Getting started

SENTINEL runs fully in mock mode — no hardware required to explore the platform.

```bash
git clone https://github.com/Ap6pack/sentinel.git
cd sentinel
./setup.sh
```

Add two values to `.env`:

```bash
VITE_CESIUM_TOKEN=       # free at https://ion.cesium.com/
SENTINEL_JWT_SECRET=     # generated automatically by setup.sh
```

Then start the stack:

```bash
docker compose -f infra/docker-compose.yml --profile basic up -d
open http://localhost:8080
```

Default credentials: `admin` / `admin`

For deployment options, hardware setup, and production configuration see
[docs/SETUP.md](docs/SETUP.md).

---

## Architecture

Six independent packages communicate exclusively through a Redis Streams event
bus. No module imports from another. Each can be deployed, tested, and run
in isolation.

```
sentinel-common   — event schema, bus client, geo utilities
sentinel-core     — auth, reverse proxy, bus→WebSocket bridge
sentinel-rf       — SDR pipeline: ADS-B, AIS, WiFi, pagers, weather sats
sentinel-osint    — OSINT collectors, identity graph, profile store
sentinel-viz      — CesiumJS globe, shader pipeline, timeline scrubber
sentinel-ai       — correlation engine, alert generation
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design,
data flow, and deployment profiles.

---

## Documentation

| Document | Description |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, module map, data flow |
| [docs/SETUP.md](docs/SETUP.md) | Installation, hardware, Docker profiles |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow, PR process |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

---

## Responsible use

SENTINEL is a passive receive platform. ADS-B, AIS, and weather satellite
signals are intentionally broadcast and legal to receive. Public OSINT sources
are used within their terms of service.

WiFi monitor mode and pager decoding are subject to jurisdiction-specific
regulations. This software is intended for research, education, and authorised
security work only.

---

## Licence

Apache 2.0 — see [LICENSE](LICENSE).