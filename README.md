# SENTINEL

**Open-source spatial intelligence platform — RF signals, OSINT, and 3D geospatial visualisation in one stack.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status: Pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)]()

SENTINEL fuses three intelligence layers that have never been combined in an open-source tool:

- **Layer 1 — Physical RF** — ADS-B aircraft, AIS vessels, WiFi/Bluetooth scanning, pager decoding, weather satellites via a $25 RTL-SDR dongle
- **Layer 2 — Internet OSINT** — fitness route analysis, review profile linking, Wi-Fi geolocation, public records — building identity-linked geo-profiles from public data
- **Layer 3 — 3D Globe** — CesiumJS visualisation with live data overlays, shader modes (NVG, FLIR, CRT), satellite tracking, and 4D temporal replay

All three layers are independently deployable modules connected by a shared event bus. A platform wrapper ties them together behind a single authenticated interface.

---

## What it looks like

> Screenshots coming at M3 — local SDR aircraft on the 3D globe.

---

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/sentinel.git
cd sentinel
cp .env.example .env
# Edit .env — add your SENTINEL_JWT_SECRET and VITE_CESIUM_TOKEN
docker compose --profile basic up -d
open http://localhost:8080
```

Default login: `admin` / `admin` — **change immediately** via `SENTINEL_ADMIN_PASSWORD` in `.env`.

No SDR hardware? Set `SENTINEL_RF_MOCK=true` in `.env` to replay fixture data.

---

## Architecture

Five independent Python packages + one JavaScript frontend, communicating only through a Redis Streams event bus:

```
sentinel-common   — shared EventEnvelope schema, bus client, geo utils
sentinel-core     — auth, reverse proxy, bus→WebSocket bridge, Docker orchestration
sentinel-rf       — SDR pipeline: ADS-B, AIS, WiFi, BT, pagers, weather sats
sentinel-osint    — OSINT collectors, identity graph linker, profile store
sentinel-viz      — CesiumJS 3D globe, shader pipeline, timeline scrubber
sentinel-ai       — Claude API correlation engine, alert generation
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

---

## Hardware

| Hardware | Purpose | Price |
|---|---|---|
| RTL-SDR dongle (RTL2832U) | All RF features | ~$25 |
| WiFi adapter (monitor mode) | WiFi scanning | ~$20 |
| GPS unit | Location tagging | ~$10 |

Everything works without hardware using `SENTINEL_RF_MOCK=true`.

---

## Build status (milestones)

- [ ] M0 — monorepo running, Redis healthy, mock events on bus
- [ ] M1 — RF standalone: SDR aircraft on sentinel-rf Leaflet map
- [ ] M2 — Globe standalone: CesiumJS globe with OpenSky + satellites
- [ ] M3 — RF → Globe: local dump1090 replaces OpenSky *(public release)*
- [ ] M4 — OSINT profile: identity-linked geo-profile from public data
- [ ] M5 — Unified wrapper: all layers behind single auth at :8080
- [ ] M6 — Profile pins on globe
- [ ] M7 — AI alert: BSSID match fires correlation alert
- [ ] M8 — Full stack demo

---

## Project structure

```
sentinel/
├── packages/
│   ├── sentinel-common/     # Shared contracts — read first
│   ├── sentinel-core/       # Platform wrapper
│   ├── sentinel-rf/         # RF/SDR layer
│   ├── sentinel-osint/      # OSINT layer
│   ├── sentinel-viz/        # 3D globe frontend
│   └── sentinel-ai/         # Correlation engine
├── infra/                   # Docker Compose, nginx
├── docs/                    # Architecture, hardware guide
├── tests/                   # Integration tests
├── CLAUDE.md                # Claude Code meta-skill (read first)
└── SKILL-*.md               # Per-module agent skill files
```

---

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.
Read [CLAUDE.md](CLAUDE.md) before using Claude Code on this repo.

---

## Licence

Apache 2.0 — see [LICENSE](LICENSE).
