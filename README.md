# SENTINEL

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-51%20passing-brightgreen)]()
[![Status](https://img.shields.io/badge/status-active%20development-blue)]() 

> *Open-source spatial intelligence — RF signals, OSINT, and live geospatial
> data fused into a single operational picture.*

---

## Overview

Most geospatial intelligence tools are either cloud-hosted dashboards
that require your data to leave your network, or single-purpose SDR
applications that do one thing well. SENTINEL is neither.

It connects a physical radio receiver to an identity correlation engine
to a 3D globe, all running locally, all open-source. A signal picked
up by a $25 dongle can be cross-referenced against public records and
surfaced as an alert on the same globe tracking aircraft overhead.

The three layers RF collection, OSINT correlation, and visualisation —
are independent modules. Run one, run all three, or replace any layer
with your own implementation. The event bus is the only contract between
them.

No cloud dependency. No subscription. Self-hosted.

![Full stack screenshot — aircraft tracks, OSINT profile pins, and AI alerts](docs/screenshots/TODO.png)

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
docker compose --profile basic up -d
open http://localhost:8080
```

Default credentials: `admin` / `admin`

For deployment options, hardware setup, and production configuration see
[docs/SETUP](docs/SETUP.md).

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

See [docs/ARCHITECTURE](docs/ARCHITECTURE.md) for the full design,
data flow, and deployment profiles.

---

## Documentation

| Document | Description |
|---|---|
| [docs/ARCHITECTURE](docs/ARCHITECTURE.md) | System design, module map, data flow |
| [docs/SETUP](docs/SETUP.md) | Installation, hardware, Docker profiles |
| [CONTRIBUTING](CONTRIBUTING.md) | Development workflow, PR process |
| [CHANGELOG](CHANGELOG.md) | Release history |

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