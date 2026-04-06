

from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

from sentinel_ai.engine.identifier import match_identifiers


def test_bssid_match():
    events = [
        EventEnvelope(
            source="rf", kind=EventKind.WIFI, entity_id="WIFI-AA:BB:CC:DD:EE:FF",
            lat=51.5074, lon=-0.1278,
            payload={"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "HomeNetwork_5G"},
        ),
    ]
    profiles = [
        {
            "entity_id": "profile-abc123",
            "lat": 51.5075,
            "lon": -0.1279,
            "identifiers": {"bssid": "AA:BB:CC:DD:EE:FF"},
        },
    ]

    matches = match_identifiers(events, profiles)
    assert len(matches) == 1
    event, profile, reason, confidence = matches[0]
    assert reason == "bssid_match"
    assert confidence == 0.90
    assert profile["entity_id"] == "profile-abc123"


def test_ssid_match_when_no_bssid():
    events = [
        EventEnvelope(
            source="rf", kind=EventKind.WIFI, entity_id="WIFI-11:22:33:44:55:66",
            lat=51.5, lon=-0.1,
            payload={"bssid": "11:22:33:44:55:66", "ssid": "CoffeeShop_WiFi"},
        ),
    ]
    profiles = [
        {
            "entity_id": "profile-xyz",
            "lat": 51.5,
            "lon": -0.1,
            "identifiers": {"ssid": "CoffeeShop_WiFi"},
        },
    ]

    matches = match_identifiers(events, profiles)
    assert len(matches) == 1
    _, _, reason, confidence = matches[0]
    assert reason == "ssid_match"
    assert confidence == 0.55


def test_bssid_takes_priority_over_ssid():
    """When both BSSID and SSID match, only BSSID match is returned."""
    events = [
        EventEnvelope(
            source="rf", kind=EventKind.WIFI, entity_id="WIFI-AA:BB:CC:DD:EE:FF",
            lat=51.5, lon=-0.1,
            payload={"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "MyNetwork"},
        ),
    ]
    profiles = [
        {
            "entity_id": "profile-1",
            "lat": 51.5,
            "lon": -0.1,
            "identifiers": {"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "MyNetwork"},
        },
    ]

    matches = match_identifiers(events, profiles)
    assert len(matches) == 1
    assert matches[0][2] == "bssid_match"


def test_no_match_for_non_wifi_events():
    events = [
        EventEnvelope(
            source="rf", kind=EventKind.AIRCRAFT, entity_id="AC-ABC123",
            lat=51.5, lon=-0.1,
            payload={"hex": "ABC123", "flight": "BA123"},
        ),
    ]
    profiles = [
        {
            "entity_id": "profile-1",
            "lat": 51.5,
            "lon": -0.1,
            "identifiers": {"bssid": "AA:BB:CC:DD:EE:FF"},
        },
    ]

    matches = match_identifiers(events, profiles)
    assert len(matches) == 0


def test_no_match_when_bssid_differs():
    events = [
        EventEnvelope(
            source="rf", kind=EventKind.WIFI, entity_id="WIFI-11:22:33:44:55:66",
            lat=51.5, lon=-0.1,
            payload={"bssid": "11:22:33:44:55:66", "ssid": "Other"},
        ),
    ]
    profiles = [
        {
            "entity_id": "profile-1",
            "lat": 51.5,
            "lon": -0.1,
            "identifiers": {"bssid": "AA:BB:CC:DD:EE:FF"},
        },
    ]

    matches = match_identifiers(events, profiles)
    assert len(matches) == 0
