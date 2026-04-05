# SKILL: sentinel-core — Platform wrapper & orchestration

## Purpose
This skill governs all work in `packages/sentinel-core/`. It covers the unified
auth system, the bus bridge (Redis → WebSocket → browser), the reverse proxy
that unifies all modules under one origin, the health aggregator, and the
Docker Compose configuration. Read this before touching auth, the proxy config,
or the Docker setup.

---

## What this module does
`sentinel-core` is the glue that binds the three layers into a single platform.
It provides: JWT authentication shared across all modules; a reverse proxy so
all APIs and the frontend are served from a single origin; a bus bridge that
forwards filtered events from Redis Streams to connected browser WebSocket
clients; a unified health dashboard; and the Docker Compose profiles that
orchestrate the entire stack.

---

## Repository layout

```
packages/sentinel-core/
├── sentinel_core/
│   ├── app.py                 # FastAPI entry point
│   ├── auth/
│   │   ├── middleware.py      # JWT validation middleware
│   │   ├── tokens.py          # Issue / verify JWTs
│   │   └── users.py           # User store (single-user for v1.0)
│   ├── bridge/
│   │   └── bus_bridge.py      # Redis Streams → WebSocket fan-out
│   ├── proxy/
│   │   └── proxy.py           # httpx reverse proxy routes
│   ├── health/
│   │   └── aggregator.py      # Polls all module /health endpoints
│   └── config.py
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.history.yml
│   └── nginx/
│       └── sentinel.conf      # Optional nginx front-end proxy
└── pyproject.toml
```

---

## Authentication — JWT shared across all modules

Every request to any sentinel module (rf, osint, viz, ai) must carry a valid
JWT issued by sentinel-core. Modules validate the JWT without calling back to
core — they share the secret from `SENTINEL_JWT_SECRET`.

### Token issuance

```python
# sentinel_core/auth/tokens.py
import os, time, jwt

SECRET = os.environ["SENTINEL_JWT_SECRET"]
ALGORITHM = "HS256"
TTL_SECONDS = 3600 * 8   # 8-hour sessions

def issue_token(username: str) -> str:
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + TTL_SECONDS,
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    """Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
```

### Auth middleware (applies to sentinel-core routes)

```python
# sentinel_core/auth/middleware.py
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer
from sentinel_core.auth.tokens import verify_token

bearer = HTTPBearer(auto_error=False)

async def require_auth(request: Request):
    creds = await bearer(request)
    if not creds:
        raise HTTPException(401, "Missing token")
    try:
        payload = verify_token(creds.credentials)
        request.state.user = payload["sub"]
    except Exception:
        raise HTTPException(401, "Invalid token")
```

### How modules validate tokens (without calling core)

```python
# In each module's middleware — same code, shared secret from env
from fastapi import Request, HTTPException
import jwt, os

SECRET = os.environ["SENTINEL_JWT_SECRET"]

async def validate_upstream_token(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        jwt.decode(auth[7:], SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
```

Add this as a FastAPI dependency on the module's router:

```python
from fastapi import APIRouter, Depends
router = APIRouter(dependencies=[Depends(validate_upstream_token)])
```

---

## Bus bridge — Redis Streams → WebSocket

The bus bridge is the most performance-sensitive component in sentinel-core.
It reads from Redis Streams, applies per-client filter specs, and fans out to
all connected WebSocket clients.

```python
# sentinel_core/bridge/bus_bridge.py
import asyncio, json, logging
from typing import Any
import redis.asyncio as redis
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

STREAM = "sentinel:events"

class BusBridge:
    def __init__(self, redis_url: str):
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._clients: dict[str, tuple[WebSocket, dict]] = {}  # client_id → (ws, filter_spec)

    async def connect(self, ws: WebSocket, client_id: str):
        await ws.accept()
        self._clients[client_id] = (ws, {})
        logger.info(f"[bridge] client {client_id} connected ({len(self._clients)} total)")
        try:
            # Listen for filter spec message from client
            msg = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
            if msg.get("type") == "filter":
                self._clients[client_id] = (ws, msg.get("spec", {}))
        except asyncio.TimeoutError:
            pass   # No filter spec — forward everything

    def disconnect(self, client_id: str):
        self._clients.pop(client_id, None)
        logger.info(f"[bridge] client {client_id} disconnected")

    def _matches_filter(self, envelope: dict, spec: dict) -> bool:
        if not spec:
            return True
        # Filter by kind list
        kinds = spec.get("kinds")
        if kinds and envelope.get("kind") not in kinds:
            return False
        # Filter by bounding box [min_lat, min_lon, max_lat, max_lon]
        bbox = spec.get("bbox")
        if bbox:
            lat, lon = envelope.get("lat"), envelope.get("lon")
            if lat is None or lon is None:
                return True  # No coordinates — don't filter out
            if not (bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3]):
                return False
        return True

    async def broadcast_loop(self):
        """Reads from Redis Streams and fans out to WebSocket clients."""
        last_id = "$"   # Only new messages
        while True:
            try:
                results = await self._redis.xread({STREAM: last_id}, count=100, block=500)
                for _, messages in (results or []):
                    for msg_id, fields in messages:
                        last_id = msg_id
                        try:
                            envelope = json.loads(fields["data"])
                        except Exception:
                            continue
                        dead = []
                        for cid, (ws, spec) in list(self._clients.items()):
                            if self._matches_filter(envelope, spec):
                                try:
                                    await ws.send_json(envelope)
                                except Exception:
                                    dead.append(cid)
                        for cid in dead:
                            self.disconnect(cid)
            except Exception as e:
                logger.warning(f"[bridge] Redis error: {e}")
                await asyncio.sleep(2)
```

Mount the WebSocket endpoint:

```python
# sentinel_core/app.py (excerpt)
import uuid
from fastapi import WebSocket, WebSocketDisconnect, Depends
from sentinel_core.bridge.bus_bridge import BusBridge

bridge = BusBridge(redis_url=settings.redis_url)

@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    client_id = str(uuid.uuid4())
    await bridge.connect(websocket, client_id)
    try:
        while True:
            await websocket.receive_text()  # Keep alive
    except WebSocketDisconnect:
        bridge.disconnect(client_id)

@app.on_event("startup")
async def startup():
    asyncio.create_task(bridge.broadcast_loop())
```

---

## Reverse proxy (proxy.py)

Routes all module APIs under the sentinel-core origin so the browser never
needs to know individual module ports.

```python
# sentinel_core/proxy/proxy.py
import httpx
from fastapi import APIRouter, Request, Response

router = APIRouter()

MODULE_ROUTES = {
    "/rf":    "http://localhost:5050",
    "/osint": "http://localhost:5001",
    "/ai":    "http://localhost:5002",
}

@router.api_route("/rf/{path:path}", methods=["GET","POST","PUT","DELETE"])
@router.api_route("/osint/{path:path}", methods=["GET","POST","PUT","DELETE"])
@router.api_route("/ai/{path:path}", methods=["GET","POST","PUT","DELETE"])
async def proxy(request: Request, path: str):
    prefix = "/" + request.url.path.split("/")[1]
    target = MODULE_ROUTES.get(prefix)
    if not target:
        return Response(status_code=404)
    url = f"{target}/{path}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            content=await request.body(),
            params=dict(request.query_params),
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
    )
```

The viz frontend (`sentinel-viz`) is served as static files from sentinel-core
at the root path `/`. Build it with `vite build` and mount the `dist/` folder:

```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="sentinel-viz-dist", html=True), name="viz")
```

---

## Health aggregator

```python
# sentinel_core/health/aggregator.py
import asyncio, httpx
from datetime import datetime, timezone

MODULE_HEALTH_URLS = {
    "rf":    "http://localhost:5050/api/v1/health",
    "osint": "http://localhost:5001/api/v1/health",
    "ai":    "http://localhost:5002/api/v1/health",
}

async def aggregate_health() -> dict:
    results = {}
    async with httpx.AsyncClient(timeout=3.0) as c:
        for name, url in MODULE_HEALTH_URLS.items():
            try:
                r = await c.get(url)
                results[name] = r.json()
            except Exception as e:
                results[name] = {"status": "unreachable", "error": str(e)}
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "modules": results,
        "overall": "ok" if all(v.get("status") == "ok" for v in results.values()) else "degraded",
    }
```

---

## Docker Compose configuration

```yaml
# infra/docker-compose.yml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redis_data:/data]
    command: redis-server --appendonly yes

  sentinel-core:
    build: ../packages/sentinel-core
    ports: ["8080:8080"]
    environment:
      SENTINEL_JWT_SECRET: ${SENTINEL_JWT_SECRET:?required}
      SENTINEL_REDIS_URL: redis://redis:6379
    depends_on: [redis]
    volumes:
      - ../packages/sentinel-viz/dist:/app/sentinel-viz-dist:ro

  sentinel-rf:
    build: ../packages/sentinel-rf
    ports: ["5050:5050"]
    privileged: true              # Required for USB SDR device access
    devices:
      - /dev/bus/usb:/dev/bus/usb
    environment:
      SENTINEL_JWT_SECRET: ${SENTINEL_JWT_SECRET}
      SENTINEL_REDIS_URL: redis://redis:6379
      SENTINEL_RF_MOCK: ${SENTINEL_RF_MOCK:-false}
    depends_on: [redis]

  sentinel-osint:
    build: ../packages/sentinel-osint
    ports: ["5001:5001"]
    environment:
      SENTINEL_JWT_SECRET: ${SENTINEL_JWT_SECRET}
      SENTINEL_REDIS_URL: redis://redis:6379
      SENTINEL_WIGLE_API_KEY: ${SENTINEL_WIGLE_API_KEY:-}
    depends_on: [redis]

  sentinel-ai:
    build: ../packages/sentinel-ai
    ports: ["5002:5002"]
    environment:
      SENTINEL_JWT_SECRET: ${SENTINEL_JWT_SECRET}
      SENTINEL_REDIS_URL: redis://redis:6379
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:?required}
    depends_on: [redis]

volumes:
  redis_data:
```

### Docker Compose profiles

| Profile | Services started | Use case |
|---|---|---|
| `basic` | redis, core, rf, viz | Development without OSINT or AI |
| `full` | all services | Full platform |
| `history` | full + postgres | Production with persistent storage |
| `mock` | all with `SENTINEL_RF_MOCK=true` | CI and development without hardware |

Start with: `docker compose --profile basic up -d`

---

## First-run setup checklist

1. Copy `.env.example` to `.env`
2. Generate `SENTINEL_JWT_SECRET`: `python3 -c "import secrets; print(secrets.token_hex(32))"`
3. Set `VITE_CESIUM_TOKEN` in `packages/sentinel-viz/.env.local`
4. Build the viz frontend: `cd packages/sentinel-viz && npm run build`
5. Run `docker compose --profile basic up -d`
6. Open `http://localhost:8080` — default credentials are `admin` / `admin`
7. Change credentials immediately via `SENTINEL_ADMIN_PASSWORD` env var

---

## Common mistakes to avoid

- **Do not** expose individual module ports publicly — everything should go
  through sentinel-core's proxy
- **Do not** use `docker compose up` without `--profile` — it starts no services
- **Do not** commit `.env` files — `.env.example` only
- **Do not** set `SENTINEL_JWT_SECRET` to a static value in docker-compose.yml —
  always require it from the environment with the `${VAR:?required}` syntax
- **Do not** run `sentinel-rf` without `privileged: true` — USB device access
  will silently fail
