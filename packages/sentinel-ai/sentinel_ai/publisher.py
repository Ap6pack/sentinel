

from __future__ import annotations

import logging

from sentinel_common.bus import BusPublisher
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

from .models.alert import AlertRecord

logger = logging.getLogger(__name__)


async def publish_alert(bus: BusPublisher, alert: AlertRecord) -> None:
    """Publish an AlertRecord as an EventEnvelope to the bus."""
    envelope = EventEnvelope(
        source="ai",
        kind=EventKind.ALERT,
        lat=alert.lat,
        lon=alert.lon,
        entity_id=alert.id,
        payload={
            "confidence": alert.confidence,
            "summary": alert.summary,
            "reasoning": alert.reasoning,
            "recommended_action": alert.recommended_action,
            "linked_entity_ids": alert.linked_entity_ids,
        },
    )
    await bus.publish(envelope)
    logger.info("[ai] published alert %s (confidence=%.2f)", alert.id, alert.confidence)
