

from sentinel_osint.linker.builder import build_profile
from sentinel_osint.models.raw import RawRecord


def _make_raw(id_: str, source: str, source_id: str, lat=None, lon=None, raw_data=None):
    return RawRecord(
        id=id_,
        source=source,
        source_id=source_id,
        lat=lat,
        lon=lon,
        raw_data=raw_data or {},
    )


def test_build_profile_basic():
    records = {
        "r1": _make_raw("r1", "wigle", "AA:BB:CC", lat=51.5, lon=-0.1, raw_data={"ssid": "Home"}),
        "r2": _make_raw("r2", "strava", "athlete-123", lat=51.51, lon=-0.09),
    }
    profile = build_profile(["r1", "r2"], records)

    assert profile.entity_id.startswith("profile-")
    assert profile.lat == 51.5  # wigle has higher priority than strava
    assert profile.lon == -0.1
    assert profile.confidence == 0.4  # 2 * 0.2
    assert set(profile.sources) == {"wigle", "strava"}
    assert profile.identifiers["bssid"] == "AA:BB:CC"
    assert profile.identifiers["strava_id"] == "athlete-123"
    assert profile.raw_ids == ["r1", "r2"]


def test_build_profile_source_priority():
    """Property source should take coordinate priority over wigle."""
    records = {
        "r1": _make_raw("r1", "wigle", "BB:CC", lat=51.5, lon=-0.1),
        "r2": _make_raw("r2", "property", "prop-456", lat=51.52, lon=-0.08),
    }
    profile = build_profile(["r1", "r2"], records)
    assert profile.lat == 51.52  # property has priority=4 > wigle=3
    assert profile.lon == -0.08


def test_build_profile_no_coords():
    records = {
        "r1": _make_raw("r1", "strava", "ath-1"),
    }
    profile = build_profile(["r1"], records)
    assert profile.lat is None
    assert profile.lon is None


def test_build_profile_confidence_cap():
    records = {f"r{i}": _make_raw(f"r{i}", "wigle", f"net-{i}") for i in range(10)}
    profile = build_profile(list(records.keys()), records)
    assert profile.confidence == 0.99  # capped
