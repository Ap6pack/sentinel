

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sentinel_common.bus import BusPublisher
from sentinel_common.config import settings

from .api.health import health_router
from .api.routes import routes_router
from .db import engine
from .models.base import Base

logger = logging.getLogger(__name__)

bus: BusPublisher | None = None

DB_CONNECT_RETRIES = 10
DB_CONNECT_DELAY = 1.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bus
    # Create tables — retry in case Postgres is still accepting connections
    for attempt in range(1, DB_CONNECT_RETRIES + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception as e:
            if attempt == DB_CONNECT_RETRIES:
                raise
            logger.warning(
                "[osint] DB connect attempt %d/%d failed: %s — retrying in %ss",
                attempt, DB_CONNECT_RETRIES, e, DB_CONNECT_DELAY,
            )
            await asyncio.sleep(DB_CONNECT_DELAY)
    bus = BusPublisher(redis_url=settings.redis_url)
    logger.info("[osint] started — bus connected")
    yield
    await bus.close()
    logger.info("[osint] shutdown complete")


app = FastAPI(title="SENTINEL OSINT", lifespan=lifespan)
app.include_router(health_router)
app.include_router(routes_router)
