# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from __future__ import annotations

import asyncio
import logging

from flask import Flask
from flask_socketio import SocketIO

from sentinel_common.bus import BusPublisher
from sentinel_common.config import settings

from .api.health import decoder_registry, health_bp
from .api.routes import routes_bp
from .config import rf_settings
from .decoders.adsb import ADSBDecoder
from .publisher import RFPublisher

logger = logging.getLogger(__name__)


def create_app() -> tuple[Flask, SocketIO]:
    """Create and configure the Flask-SocketIO application."""
    app = Flask(__name__)
    import os

    app.config["SECRET_KEY"] = os.environ.get("SENTINEL_JWT_SECRET", os.urandom(32).hex())

    socketio = SocketIO(app, async_mode="gevent", cors_allowed_origins="*")

    app.register_blueprint(health_bp)
    app.register_blueprint(routes_bp)

    return app, socketio


async def run_decoders() -> None:
    """Start all configured decoders and publish events to the bus."""
    bus = BusPublisher(redis_url=settings.redis_url)
    publisher = RFPublisher(bus=bus)

    adsb = ADSBDecoder(device_index=rf_settings.adsb_device_index)
    decoder_registry["adsb"] = adsb

    async def on_event(envelope):
        await publisher.publish(envelope)
        logger.debug("[%s] published %s", envelope.source, envelope.entity_id)

    await adsb.start(on_event)
    logger.info("All decoders started (mock=%s)", rf_settings.mock)


def main() -> None:
    """Entry point for running the Flask-SocketIO server with decoders."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    app, socketio = create_app()

    loop = asyncio.new_event_loop()
    loop.run_until_complete(run_decoders())

    logger.info("Starting Flask-SocketIO on :5050")
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
