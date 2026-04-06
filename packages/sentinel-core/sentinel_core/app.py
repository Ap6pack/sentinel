

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth.middleware import require_auth
from .auth.tokens import issue_token
from .auth.users import authenticate
from .bridge.bus_bridge import BusBridge
from .config import core_settings
from .health.aggregator import aggregate_health
from .proxy.proxy import router as proxy_router

logger = logging.getLogger(__name__)

bridge = BusBridge(redis_url=core_settings.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the bus bridge broadcast loop on startup."""
    task = asyncio.create_task(bridge.broadcast_loop())
    logger.info("sentinel-core started on :%d", core_settings.port)
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="SENTINEL Core", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Auth routes (public) ---


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/v1/auth/login")
async def login(body: LoginRequest):
    if not authenticate(body.username, body.password):
        raise HTTPException(401, "Invalid credentials")
    token = issue_token(body.username)
    return {"token": token, "username": body.username}


# --- Health (public) ---


@app.get("/api/v1/health")
async def health():
    return await aggregate_health()


# --- WebSocket bus bridge (no auth for v1.0 — browser can't send headers on WS) ---


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    client_id = str(uuid.uuid4())
    await bridge.connect(websocket, client_id)
    try:
        while True:
            await websocket.receive_text()  # Keep alive
    except WebSocketDisconnect:
        bridge.disconnect(client_id)
    except Exception:
        bridge.disconnect(client_id)


# --- Reverse proxy (auth-protected) ---

app.include_router(proxy_router, dependencies=[Depends(require_auth)])


# --- Entry point ---


def main() -> None:
    import uvicorn

    logging.basicConfig(
        level=getattr(logging, core_settings.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    uvicorn.run(
        "sentinel_core.app:app",
        host="0.0.0.0",
        port=core_settings.port,
        log_level=core_settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
