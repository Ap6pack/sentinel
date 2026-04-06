

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinel_common.bus import BusPublisher

from .api.health import health_router
from .api.routes import routes_router
from .config import ai_settings
from .db import AsyncSessionLocal
from .engine.consumer import AiConsumer
from .engine.correlator import correlate_batch
from .engine.identifier import match_identifiers
from .engine.spatial import find_profiles_for_batch
from .engine.window import EventWindow
from .publisher import publish_alert

logger = logging.getLogger(__name__)

bus = BusPublisher(redis_url=ai_settings.redis_url)


async def _on_window_ready(events: list) -> None:
    """Called when the event window flushes — runs correlation pipeline."""
    from sentinel_common.envelope import EventEnvelope

    # 1. Spatial join: find nearby OSINT profiles
    profiles = await find_profiles_for_batch(events)

    # 2. Identifier match: BSSID/SSID linking
    id_matches = match_identifiers(events, profiles)

    # 3. If we have identifier matches, boost context for Claude
    matched_profiles = profiles.copy()
    for _event, profile, reason, confidence in id_matches:
        # Annotate profile with match info for the correlator
        profile_copy = profile.copy()
        profile_copy["match_reason"] = reason
        profile_copy["match_confidence"] = confidence
        if profile_copy not in matched_profiles:
            matched_profiles.append(profile_copy)

    # 4. Call Claude correlator
    if not matched_profiles:
        logger.info("[pipeline] no profiles matched for %d events, skipping", len(events))
        return

    alert = await correlate_batch(events, matched_profiles)
    if alert is None:
        return

    # 5. Persist alert
    async with AsyncSessionLocal() as db:
        db.add(alert)
        await db.commit()

    # 6. Publish alert to bus
    await publish_alert(bus, alert)


window = EventWindow(on_window_ready=_on_window_ready)
consumer = AiConsumer(window=window)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the event window and consumer on startup."""
    await window.start()
    await consumer.start()
    logger.info("sentinel-ai started on :%d", ai_settings.port)
    yield
    await consumer.stop()
    await window.stop()


app = FastAPI(title="SENTINEL AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(routes_router)


def main() -> None:
    import uvicorn

    logging.basicConfig(
        level=getattr(logging, ai_settings.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    uvicorn.run(
        "sentinel_ai.app:app",
        host="0.0.0.0",
        port=ai_settings.port,
        log_level=ai_settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
