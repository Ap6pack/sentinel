# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

import pytest
from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind


def test_roundtrip_redis():
    env = EventEnvelope(
        source="rf",
        kind=EventKind.AIRCRAFT,
        lat=51.5,
        lon=-0.1,
        entity_id="TEST-1",
        payload={"callsign": "TST001"},
    )
    raw = env.to_redis()
    assert "data" in raw
    assert isinstance(raw["data"], str)

    restored = EventEnvelope.from_redis(raw)
    assert restored.entity_id == env.entity_id
    assert restored.payload["callsign"] == "TST001"
    assert restored.lat == 51.5
    assert restored.lon == -0.1
    assert restored.kind == EventKind.AIRCRAFT
    assert restored.source == "rf"


def test_invalid_lat():
    with pytest.raises(ValueError, match="lat out of range"):
        EventEnvelope(source="rf", kind=EventKind.AIRCRAFT, lat=200.0, lon=0.0, entity_id="BAD")


def test_invalid_lon():
    with pytest.raises(ValueError, match="lon out of range"):
        EventEnvelope(source="rf", kind=EventKind.AIRCRAFT, lat=0.0, lon=300.0, entity_id="BAD")


def test_none_coords_valid():
    env = EventEnvelope(source="osint", kind=EventKind.PROFILE, entity_id="PROFILE-1")
    assert env.lat is None
    assert env.lon is None


def test_default_fields():
    env = EventEnvelope(source="rf", kind=EventKind.VESSEL, entity_id="MMSI-123")
    assert env.id  # uuid generated
    assert env.ts  # timestamp generated
    assert env.payload == {}
    assert env.alt_m is None


def test_boundary_coords():
    env = EventEnvelope(
        source="rf", kind=EventKind.AIRCRAFT, lat=90.0, lon=180.0, entity_id="EDGE"
    )
    assert env.lat == 90.0
    assert env.lon == 180.0

    env2 = EventEnvelope(
        source="rf", kind=EventKind.AIRCRAFT, lat=-90.0, lon=-180.0, entity_id="EDGE2"
    )
    assert env2.lat == -90.0
    assert env2.lon == -180.0
