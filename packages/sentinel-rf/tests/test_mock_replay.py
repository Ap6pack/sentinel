# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

import asyncio

import pytest

from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind
from sentinel_rf.decoders.adsb import ADSBDecoder


@pytest.fixture(autouse=True)
def enable_mock(monkeypatch):
    """Force mock mode for all tests in this module."""
    monkeypatch.setattr("sentinel_rf.decoders.adsb.rf_settings.mock", True)


async def test_mock_replay_produces_events():
    """Mock mode should replay fixture aircraft and produce EventEnvelope objects."""
    decoder = ADSBDecoder(poll_interval=0.01)
    decoder._running = True

    received: list[EventEnvelope] = []

    async def collect(envelope: EventEnvelope):
        received.append(envelope)
        if len(received) >= 3:
            decoder._running = False

    await decoder.run(collect)

    assert len(received) == 3
    for env in received:
        assert isinstance(env, EventEnvelope)
        assert env.source == "rf"
        assert env.kind == EventKind.AIRCRAFT
        assert env.lat is not None
        assert env.lon is not None
        assert env.entity_id.startswith("ICAO-")


async def test_mock_replay_correct_entities():
    """Mock replay should produce the 3 valid aircraft from the fixture."""
    decoder = ADSBDecoder(poll_interval=0.01)
    decoder._running = True

    received: list[EventEnvelope] = []

    async def collect(envelope: EventEnvelope):
        received.append(envelope)
        if len(received) >= 3:
            decoder._running = False

    await decoder.run(collect)

    entity_ids = {e.entity_id for e in received}
    assert entity_ids == {"ICAO-3C4A6F", "ICAO-40762F", "ICAO-A1B2C3"}


async def test_mock_replay_payload_content():
    """Verify payload fields are populated from fixture data."""
    decoder = ADSBDecoder(poll_interval=0.01)
    decoder._running = True

    received: list[EventEnvelope] = []

    async def collect(envelope: EventEnvelope):
        received.append(envelope)
        if len(received) >= 3:
            decoder._running = False

    await decoder.run(collect)

    dlh = next(e for e in received if e.entity_id == "ICAO-3C4A6F")
    assert dlh.payload["callsign"] == "DLH441"
    assert dlh.payload["speed_kts"] == 430
    assert dlh.alt_m == pytest.approx(35000 * 0.3048)


async def test_mock_replay_loops():
    """Mock mode should loop through the fixture, producing events repeatedly."""
    decoder = ADSBDecoder(poll_interval=0.01)
    decoder._running = True

    received: list[EventEnvelope] = []

    async def collect(envelope: EventEnvelope):
        received.append(envelope)
        # Wait for more than one cycle (3 valid per cycle)
        if len(received) >= 7:
            decoder._running = False

    await decoder.run(collect)

    # Should have gotten events from at least 2 replay cycles
    assert len(received) >= 6


async def test_mock_publishes_to_bus(monkeypatch):
    """Verify mock events flow through RFPublisher to a (fake) bus."""
    from sentinel_rf.publisher import RFPublisher

    published: list[EventEnvelope] = []

    class FakeBus:
        async def publish(self, envelope):
            published.append(envelope)

    publisher = RFPublisher(bus=FakeBus())

    decoder = ADSBDecoder(poll_interval=0.01)
    decoder._running = True

    events_seen = 0

    async def on_event(envelope: EventEnvelope):
        nonlocal events_seen
        await publisher.publish(envelope)
        events_seen += 1
        if events_seen >= 3:
            decoder._running = False

    await decoder.run(on_event)

    assert len(published) == 3
    for env in published:
        assert isinstance(env, EventEnvelope)
        assert env.kind == EventKind.AIRCRAFT
