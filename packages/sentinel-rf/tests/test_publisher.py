

import pytest

from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind
from sentinel_rf.publisher import RFPublisher


class FakeBus:
    def __init__(self):
        self.published: list[EventEnvelope] = []

    async def publish(self, envelope: EventEnvelope):
        self.published.append(envelope)


async def test_publish_passthrough():
    """Events with coords should pass through unchanged."""
    bus = FakeBus()
    pub = RFPublisher(bus=bus)

    env = EventEnvelope(
        source="rf", kind=EventKind.AIRCRAFT, lat=51.5, lon=-0.1, entity_id="TEST-1"
    )
    await pub.publish(env)

    assert len(bus.published) == 1
    assert bus.published[0].lat == 51.5
    assert bus.published[0].lon == -0.1


async def test_gps_enrichment():
    """Events without coords should be enriched with cached GPS."""
    bus = FakeBus()
    pub = RFPublisher(bus=bus)
    pub._gps_lat = 48.8
    pub._gps_lon = 2.3

    env = EventEnvelope(
        source="rf", kind=EventKind.WIFI, entity_id="WIFI-AA:BB:CC:DD:EE:FF"
    )
    await pub.publish(env)

    assert len(bus.published) == 1
    assert bus.published[0].lat == 48.8
    assert bus.published[0].lon == 2.3


async def test_no_gps_no_enrichment():
    """Without GPS fix, events without coords stay without coords."""
    bus = FakeBus()
    pub = RFPublisher(bus=bus)

    env = EventEnvelope(
        source="rf", kind=EventKind.WIFI, entity_id="WIFI-AA:BB:CC:DD:EE:FF"
    )
    await pub.publish(env)

    assert bus.published[0].lat is None
    assert bus.published[0].lon is None
