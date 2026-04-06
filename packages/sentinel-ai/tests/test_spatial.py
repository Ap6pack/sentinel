

import pytest

from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

from sentinel_ai.engine.spatial import find_nearby_profiles, find_profiles_for_batch


async def test_find_nearby_profiles_returns_results(httpx_mock):
    profiles = [
        {
            "entity_id": "profile-abc",
            "lat": 51.5075,
            "lon": -0.1279,
            "confidence": 0.8,
            "sources": ["wigle"],
            "identifiers": {"bssid": "AA:BB:CC:DD:EE:FF"},
        }
    ]
    httpx_mock.add_response(json=profiles)

    event = EventEnvelope(
        source="rf", kind=EventKind.WIFI, entity_id="w1",
        lat=51.5074, lon=-0.1278, payload={},
    )

    result = await find_nearby_profiles(event, osint_url="http://mock-osint:5001")
    assert len(result) == 1
    assert result[0]["entity_id"] == "profile-abc"


async def test_find_nearby_profiles_no_coords():
    event = EventEnvelope(
        source="rf", kind=EventKind.WIFI, entity_id="w1",
        payload={},
    )
    result = await find_nearby_profiles(event)
    assert result == []


async def test_find_nearby_profiles_handles_error(httpx_mock):
    httpx_mock.add_response(status_code=500)

    event = EventEnvelope(
        source="rf", kind=EventKind.WIFI, entity_id="w1",
        lat=51.5, lon=-0.1, payload={},
    )
    result = await find_nearby_profiles(event, osint_url="http://mock-osint:5001")
    assert result == []


async def test_find_profiles_for_batch_deduplicates(httpx_mock):
    profile = {
        "entity_id": "profile-abc",
        "lat": 51.5075,
        "lon": -0.1279,
        "confidence": 0.8,
        "sources": ["wigle"],
        "identifiers": {},
    }
    # Both events will return the same profile
    httpx_mock.add_response(json=[profile])
    httpx_mock.add_response(json=[profile])

    events = [
        EventEnvelope(
            source="rf", kind=EventKind.WIFI, entity_id="w1",
            lat=51.5074, lon=-0.1278, payload={},
        ),
        EventEnvelope(
            source="rf", kind=EventKind.WIFI, entity_id="w2",
            lat=51.5074, lon=-0.1278, payload={},
        ),
    ]
    result = await find_profiles_for_batch(events, osint_url="http://mock-osint:5001")
    assert len(result) == 1
