

from __future__ import annotations

import logging

from sentinel_common.bus import BusPublisher
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

from .models.profile import ProfileRecord

logger = logging.getLogger(__name__)


async def publish_profile(bus: BusPublisher, profile: ProfileRecord) -> None:
    """Publish a ProfileRecord as an EventEnvelope to the bus."""
    envelope = EventEnvelope(
        source="osint",
        kind=EventKind.PROFILE,
        lat=profile.lat,
        lon=profile.lon,
        entity_id=profile.entity_id,
        payload={
            "confidence": profile.confidence,
            "sources": profile.sources,
            "identifiers": profile.identifiers,
            "attributes": profile.attributes,
        },
    )
    await bus.publish(envelope)
    logger.info("[osint] published profile %s", profile.entity_id)


async def publish_profile_link(
    bus: BusPublisher,
    entity_a: str,
    entity_b: str,
    reason: str,
    confidence: float,
) -> None:
    """Publish a PROFILE_LINK event when two profiles are linked."""
    envelope = EventEnvelope(
        source="osint",
        kind=EventKind.PROFILE_LINK,
        entity_id=entity_a,
        payload={
            "linked_entity_id": entity_b,
            "reason": reason,
            "confidence": confidence,
        },
    )
    await bus.publish(envelope)
    logger.info("[osint] published link %s <-> %s (%s)", entity_a, entity_b, reason)
