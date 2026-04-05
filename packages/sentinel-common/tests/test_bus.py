# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

import asyncio

import pytest
import fakeredis.aioredis

from sentinel_common.bus import STREAM_NAME, BusConsumer, BusPublisher
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind


@pytest.fixture
def fake_redis_server():
    return fakeredis.aioredis.FakeServer()


@pytest.fixture
def publisher(fake_redis_server, monkeypatch):
    pub = BusPublisher.__new__(BusPublisher)
    pub._client = fakeredis.aioredis.FakeRedis(
        server=fake_redis_server, decode_responses=True
    )
    return pub


@pytest.fixture
def consumer(fake_redis_server, monkeypatch):
    cons = BusConsumer.__new__(BusConsumer)
    cons._client = fakeredis.aioredis.FakeRedis(
        server=fake_redis_server, decode_responses=True
    )
    cons._group = "test-group"
    cons._consumer = "test-consumer-1"
    cons._kinds = None
    cons._stream = STREAM_NAME
    return cons


@pytest.fixture
def filtered_consumer(fake_redis_server):
    cons = BusConsumer.__new__(BusConsumer)
    cons._client = fakeredis.aioredis.FakeRedis(
        server=fake_redis_server, decode_responses=True
    )
    cons._group = "test-group-filtered"
    cons._consumer = "test-consumer-2"
    cons._kinds = {EventKind.AIRCRAFT}
    cons._stream = STREAM_NAME
    return cons


async def test_publish_returns_stream_id(publisher):
    env = EventEnvelope(
        source="rf", kind=EventKind.AIRCRAFT, lat=51.5, lon=-0.1, entity_id="TEST-1"
    )
    msg_id = await publisher.publish(env)
    assert msg_id  # should be a Redis stream ID like "1234567890-0"
    assert "-" in msg_id


async def test_publish_consume_roundtrip(publisher, consumer):
    env = EventEnvelope(
        source="rf",
        kind=EventKind.VESSEL,
        lat=48.8,
        lon=2.3,
        entity_id="MMSI-999",
        payload={"name": "Test Vessel"},
    )
    await publisher.publish(env)

    received = []
    async for event in consumer:
        received.append(event)
        if len(received) >= 1:
            break

    assert len(received) == 1
    assert received[0].entity_id == "MMSI-999"
    assert received[0].payload["name"] == "Test Vessel"
    assert received[0].kind == EventKind.VESSEL


async def test_consumer_filters_by_kind(publisher, filtered_consumer):
    vessel = EventEnvelope(
        source="rf", kind=EventKind.VESSEL, entity_id="MMSI-111"
    )
    aircraft = EventEnvelope(
        source="rf", kind=EventKind.AIRCRAFT, lat=51.5, lon=-0.1, entity_id="ICAO-ABC"
    )
    await publisher.publish(vessel)
    await publisher.publish(aircraft)

    received = []
    async for event in filtered_consumer:
        received.append(event)
        if len(received) >= 1:
            break

    assert len(received) == 1
    assert received[0].kind == EventKind.AIRCRAFT


async def test_ensure_group_idempotent(consumer):
    await consumer.ensure_group()
    await consumer.ensure_group()  # should not raise
