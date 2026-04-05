# SKILL: sentinel-osint — OSINT aggregation & identity linking layer

## Purpose
This skill governs all work in `packages/sentinel-osint/`. It covers how to
build API collectors, how the identity linker works, the profile data model,
and how profiles are published to the bus. Read this before adding a new data
source, changing the profile schema, or touching the graph linker.

---

## What this module does
`sentinel-osint` is Layer 2 — the internet OSINT pipeline. It runs independent
async collector workers (one per data source), stores raw and enriched records
in Postgres, runs an identity graph linker that connects records across sources,
and publishes `PROFILE` and `PROFILE_LINK` events to the shared bus.

---

## Repository layout

```
packages/sentinel-osint/
├── sentinel_osint/
│   ├── app.py                   # FastAPI entry point
│   ├── api/
│   │   ├── routes.py            # REST: /profiles, /enrich, /graph
│   │   └── health.py
│   ├── collectors/
│   │   ├── base.py              # BaseCollector ABC
│   │   ├── fitness.py           # Strava / Garmin public activity API
│   │   ├── reviews.py           # Google Places reviewer profiles
│   │   ├── wigle.py             # WiGLE.net WiFi geolocation
│   │   ├── property.py          # County assessor open data
│   │   └── username.py          # Cross-platform username search
│   ├── linker/
│   │   ├── graph.py             # NetworkX identity graph
│   │   ├── scorer.py            # Link confidence scoring
│   │   └── builder.py           # Profile record assembler
│   ├── models/
│   │   ├── profile.py           # SQLAlchemy ORM models
│   │   └── raw.py               # Raw record storage
│   └── publisher.py             # Profile → EventEnvelope → bus
├── tests/
│   ├── test_linker.py
│   ├── test_fitness_collector.py
│   └── fixtures/
└── pyproject.toml
```

---

## Data model

### ProfileRecord (Postgres)

```python
# sentinel_osint/models/profile.py
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class ProfileRecord(Base):
    __tablename__ = "profiles"

    entity_id   = Column(String, primary_key=True)  # stable, e.g. "profile-uuid4"
    lat         = Column(Float)           # best-known home coordinate
    lon         = Column(Float)
    confidence  = Column(Float)           # 0.0–1.0 overall confidence
    sources     = Column(JSON)            # list of source names that contributed
    identifiers = Column(JSON)            # {"strava_id": "...", "username": "...", "ssid": "..."}
    attributes  = Column(JSON)            # {"birth_date_hint": ..., "review_count": ...}
    raw_ids     = Column(JSON)            # list of RawRecord PKs
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### RawRecord (Postgres)

```python
class RawRecord(Base):
    __tablename__ = "raw_records"

    id          = Column(String, primary_key=True)   # uuid4
    source      = Column(String, index=True)         # "strava" | "google_reviews" | "wigle" | ...
    source_id   = Column(String, index=True)         # ID within that source
    lat         = Column(Float)
    lon         = Column(Float)
    raw_data    = Column(JSON)
    collected_at = Column(DateTime, default=datetime.utcnow)
```

**Never store PII in column names.** All personal data goes into `raw_data` JSON
and `attributes` JSON. This makes it trivial to wipe a profile by nulling those
columns.

---

## BaseCollector — the pattern every collector must follow

```python
# sentinel_osint/collectors/base.py
from __future__ import annotations
import asyncio, logging, time
from abc import ABC, abstractmethod
from typing import AsyncIterator
from sentinel_osint.models.raw import RawRecord

logger = logging.getLogger(__name__)

class BaseCollector(ABC):
    name: str = "base"
    rate_limit_per_minute: int = 30      # override per source
    requires_api_key: bool = False

    def __init__(self):
        self._call_times: list[float] = []

    async def _rate_limit(self):
        """Sliding window rate limiter. Call before every API request."""
        now = time.monotonic()
        self._call_times = [t for t in self._call_times if now - t < 60]
        if len(self._call_times) >= self.rate_limit_per_minute:
            sleep_for = 60 - (now - self._call_times[0]) + 0.1
            logger.debug(f"[{self.name}] rate limit: sleeping {sleep_for:.1f}s")
            await asyncio.sleep(sleep_for)
        self._call_times.append(time.monotonic())

    @abstractmethod
    async def collect(self, lat: float, lon: float, radius_m: float) -> AsyncIterator[RawRecord]:
        """
        Yield RawRecord objects for the given area.
        Must call self._rate_limit() before each outbound HTTP request.
        Must never raise on HTTP errors — log and yield nothing for that request.
        """

    async def is_available(self) -> bool:
        """Return False if API key missing or service unreachable."""
        return True
```

---

## Fitness collector (Strava public API)

```python
# sentinel_osint/collectors/fitness.py
import httpx
from sentinel_osint.collectors.base import BaseCollector
from sentinel_osint.models.raw import RawRecord
import uuid

class FitnessCollector(BaseCollector):
    name = "strava"
    rate_limit_per_minute = 15    # Strava free tier is strict

    async def collect(self, lat, lon, radius_m):
        # Strava segment explorer: find public segments near a coordinate
        # Then fetch public leaderboards to get athlete IDs
        url = "https://www.strava.com/api/v3/segments/explore"
        params = {"bounds": f"{lat-0.05},{lon-0.05},{lat+0.05},{lon+0.05}", "activity_type": "running"}
        await self._rate_limit()
        async with httpx.AsyncClient(timeout=10) as c:
            try:
                r = await c.get(url, params=params,
                                headers={"Authorization": f"Bearer {self._token}"})
                r.raise_for_status()
                for seg in r.json().get("segments", []):
                    yield RawRecord(
                        id=str(uuid.uuid4()),
                        source="strava",
                        source_id=str(seg["id"]),
                        lat=seg["start_latlng"][0],
                        lon=seg["start_latlng"][1],
                        raw_data=seg,
                    )
            except Exception as e:
                import logging; logging.getLogger(__name__).warning(f"[strava] {e}")
```

**Route origin clustering** (how we infer home coordinates from fitness data):

```python
# sentinel_osint/collectors/fitness.py
from sklearn.cluster import DBSCAN
import numpy as np

def infer_home_coord(route_starts: list[tuple[float, float]]) -> tuple[float, float] | None:
    """
    Given a list of (lat, lon) route start points, find the most common
    origin cluster — likely home address.
    Returns None if fewer than 3 routes or no dominant cluster.
    """
    if len(route_starts) < 3:
        return None
    coords = np.array(route_starts)
    # DBSCAN with ~150m epsilon (in degrees)
    db = DBSCAN(eps=0.0013, min_samples=2, algorithm="ball_tree", metric="haversine")
    labels = db.fit_predict(np.radians(coords))
    if all(l == -1 for l in labels):
        return None
    # Return centroid of the largest cluster (excluding noise label -1)
    from collections import Counter
    most_common = Counter(l for l in labels if l != -1).most_common(1)[0][0]
    cluster_pts = coords[labels == most_common]
    return float(cluster_pts[:, 0].mean()), float(cluster_pts[:, 1].mean())
```

---

## WiGLE collector

```python
# sentinel_osint/collectors/wigle.py
import httpx, os
from .base import BaseCollector
from sentinel_osint.models.raw import RawRecord
import uuid

class WiGLECollector(BaseCollector):
    name = "wigle"
    rate_limit_per_minute = 10    # WiGLE free tier is very strict
    requires_api_key = True

    def __init__(self):
        super().__init__()
        self._api_key = os.getenv("SENTINEL_WIGLE_API_KEY", "")

    async def collect(self, lat, lon, radius_m):
        if not self._api_key:
            return
        latrange = radius_m / 111_000   # rough degrees per metre
        params = {
            "latrange1": lat - latrange, "latrange2": lat + latrange,
            "longrange1": lon - latrange, "longrange2": lon + latrange,
            "freenet": "false", "paynet": "false",
        }
        await self._rate_limit()
        async with httpx.AsyncClient(timeout=15) as c:
            try:
                r = await c.get(
                    "https://api.wigle.net/api/v2/network/search",
                    params=params,
                    headers={"Authorization": f"Basic {self._api_key}"},
                )
                r.raise_for_status()
                for net in r.json().get("results", []):
                    yield RawRecord(
                        id=str(uuid.uuid4()),
                        source="wigle",
                        source_id=net.get("netid", ""),  # BSSID
                        lat=net["trilat"],
                        lon=net["trilong"],
                        raw_data=net,
                    )
            except Exception as e:
                import logging; logging.getLogger(__name__).warning(f"[wigle] {e}")
```

---

## Identity linker

The linker maintains a NetworkX graph where nodes are `RawRecord` IDs and edges
represent discovered links. Connected components become `ProfileRecord`s.

```python
# sentinel_osint/linker/graph.py
import networkx as nx
from sentinel_osint.linker.scorer import confidence_for_link

class IdentityGraph:
    def __init__(self):
        self._g = nx.Graph()

    def add_record(self, record_id: str, metadata: dict):
        self._g.add_node(record_id, **metadata)

    def link(self, id_a: str, id_b: str, reason: str, confidence: float):
        """Add or strengthen a link between two records."""
        if self._g.has_edge(id_a, id_b):
            # Strengthen existing link — take max confidence
            existing = self._g[id_a][id_b]["confidence"]
            self._g[id_a][id_b]["confidence"] = max(existing, confidence)
        else:
            self._g.add_edge(id_a, id_b, reason=reason, confidence=confidence)

    def profiles(self) -> list[list[str]]:
        """Return list of connected components (each = one profile)."""
        return [list(c) for c in nx.connected_components(self._g) if len(c) >= 2]
```

### Link triggers — when to call `graph.link()`

| Condition | Confidence | Reason string |
|---|---|---|
| Same BSSID in WiFi RF event AND WiGLE record | 0.95 | `"bssid_match"` |
| Route origin within 50m of property centroid | 0.80 | `"spatial_home_cluster"` |
| Same username across two platforms | 0.90 | `"username_match"` |
| Same display name + city in two review profiles | 0.60 | `"name_city_match"` |
| Same profile photo hash | 0.95 | `"photo_hash_match"` |

Never link on coordinate proximity alone below 0.30 confidence. Two people can
live in the same building.

---

## Profile builder

```python
# sentinel_osint/linker/builder.py
from sentinel_osint.linker.graph import IdentityGraph
from sentinel_osint.models.profile import ProfileRecord
from sentinel_common.geo import haversine_m
import uuid

def build_profile(component: list[str], records: dict) -> ProfileRecord:
    """
    Given a connected component of record IDs and a dict of RawRecords,
    assemble a ProfileRecord with the best available coordinate and
    merged identifiers.
    """
    recs = [records[rid] for rid in component if rid in records]
    # Best coordinate = record with highest source confidence
    # Priority: property > wigle > strava > reviews
    source_priority = {"property": 4, "wigle": 3, "strava": 2, "google_reviews": 1}
    best = sorted(recs, key=lambda r: source_priority.get(r.source, 0), reverse=True)
    lat = next((r.lat for r in best if r.lat), None)
    lon = next((r.lon for r in best if r.lon), None)

    identifiers = {}
    for r in recs:
        if r.source == "strava":
            identifiers["strava_id"] = r.source_id
        elif r.source == "wigle":
            identifiers["bssid"] = r.source_id
            identifiers["ssid"] = r.raw_data.get("ssid", "")

    return ProfileRecord(
        entity_id=f"profile-{uuid.uuid4()}",
        lat=lat, lon=lon,
        confidence=min(0.99, len(recs) * 0.2),  # rough confidence scaling
        sources=list({r.source for r in recs}),
        identifiers=identifiers,
        attributes={},
        raw_ids=component,
    )
```

---

## REST endpoints

```python
# sentinel_osint/api/routes.py
from fastapi import APIRouter, Query
router = APIRouter()

@router.get("/api/v1/profiles")
async def list_profiles(lat: float = Query(...), lon: float = Query(...),
                         radius_m: float = Query(1000)):
    """Return profiles within radius_m of lat/lon. Used by sentinel-viz for map overlays."""
    ...

@router.post("/api/v1/enrich")
async def trigger_enrich(lat: float, lon: float, radius_m: float = 500):
    """
    Trigger all collectors for the given area.
    Returns immediately with a job_id; poll /api/v1/jobs/{job_id} for status.
    """
    ...

@router.get("/api/v1/graph/{entity_id}")
async def get_graph(entity_id: str):
    """Return the identity graph neighbourhood for a profile."""
    ...
```

---

## Rate limiting rules — non-negotiable

Every collector must:
1. Call `await self._rate_limit()` before **every single outbound HTTP request**
2. Implement per-source limits (see table below)
3. Respect `Retry-After` headers — if a 429 is received, sleep for the
   indicated duration before retrying
4. Log every 429 at WARNING level with the source name and URL

| Source | Max requests/minute | Notes |
|---|---|---|
| Strava | 15 | Token refresh counts as a request |
| Google Places | 20 | Shared quota across all collectors |
| WiGLE | 10 | Very aggressive rate limiting; back off immediately on 429 |
| Property APIs | 60 | Most are generous |
| Username search | 5 | Spread across platforms with randomised delay |

---

## Adding a new collector — checklist

1. Create `sentinel_osint/collectors/{name}.py` extending `BaseCollector`
2. Set `name`, `rate_limit_per_minute`, `requires_api_key` class attributes
3. Implement `collect()` as an async generator yielding `RawRecord`s
4. Add API key env var to `.env.example` if needed
5. Register in `sentinel_osint/collectors/__init__.py` registry list
6. Add link trigger logic to `sentinel_osint/linker/graph.py` if the source
   produces a linkable identifier (BSSID, username, photo hash, etc.)
7. Write at least 3 test cases using recorded HTTP fixtures (use `respx` for
   mocking `httpx` calls — never make real API calls in tests)

---

## Common mistakes to avoid

- **Do not** store collector output directly as a profile — always go through
  the linker, even for single-source records
- **Do not** run all collectors simultaneously on startup — use a job queue
  (asyncio.Queue) so enrichment is triggered by explicit requests
- **Do not** use `requests` (sync) — always use `httpx.AsyncClient`
- **Do not** hardcode bounding box sizes — always derive from `radius_m`
  parameter using the haversine approximation
- **Do not** link records with confidence below 0.20 — this creates false
  identity merges that are hard to unwind
