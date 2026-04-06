

from sentinel_osint.linker.graph import IdentityGraph
from sentinel_osint.linker.scorer import discover_links
from sentinel_osint.models.raw import RawRecord


def _raw(id_: str, source: str, source_id: str, lat=None, lon=None, raw_data=None):
    return RawRecord(
        id=id_,
        source=source,
        source_id=source_id,
        lat=lat,
        lon=lon,
        raw_data=raw_data or {},
    )


def test_bssid_match_links_wigle_records():
    r1 = _raw("w1", "wigle", "net-1", raw_data={"netid": "AA:BB:CC"})
    r2 = _raw("w2", "wigle", "net-2", raw_data={"netid": "AA:BB:CC"})
    r3 = _raw("w3", "wigle", "net-3", raw_data={"netid": "DD:EE:FF"})

    graph = IdentityGraph()
    for r in [r1, r2, r3]:
        graph.add_record(r.id, {"source": r.source})

    discover_links([r1, r2, r3], graph)

    assert graph.edge_count == 1
    profiles = graph.profiles()
    assert len(profiles) == 1
    assert set(profiles[0]) == {"w1", "w2"}


def test_username_match_across_platforms():
    r1 = _raw("u1", "username_github", "johndoe")
    r2 = _raw("u2", "username_twitter", "johndoe")
    r3 = _raw("u3", "username_reddit", "johndoe")
    r4 = _raw("u4", "username_github", "janedoe")

    graph = IdentityGraph()
    for r in [r1, r2, r3, r4]:
        graph.add_record(r.id, {"source": r.source})

    discover_links([r1, r2, r3, r4], graph)

    profiles = graph.profiles()
    assert len(profiles) == 1
    assert set(profiles[0]) == {"u1", "u2", "u3"}


def test_name_city_match_links_reviews():
    r1 = _raw(
        "rv1",
        "google_reviews",
        "auth-1",
        lat=51.50,
        lon=-0.12,
        raw_data={"author_name": "John Smith"},
    )
    r2 = _raw(
        "rv2",
        "google_reviews",
        "auth-2",
        lat=51.51,
        lon=-0.11,
        raw_data={"author_name": "John Smith"},
    )
    # Different city — too far apart
    r3 = _raw(
        "rv3",
        "google_reviews",
        "auth-3",
        lat=52.50,
        lon=1.00,
        raw_data={"author_name": "John Smith"},
    )

    graph = IdentityGraph()
    for r in [r1, r2, r3]:
        graph.add_record(r.id, {"source": r.source})

    discover_links([r1, r2, r3], graph)

    profiles = graph.profiles()
    assert len(profiles) == 1
    assert set(profiles[0]) == {"rv1", "rv2"}


def test_spatial_home_cluster_links_strava_to_property():
    # Route origin within 50m of property
    route = _raw("s1", "strava", "seg-1", lat=51.5000, lon=-0.1000)
    prop = _raw("p1", "property", "prop-1", lat=51.5001, lon=-0.1001)
    # Another property too far away
    far_prop = _raw("p2", "property", "prop-2", lat=52.0, lon=-0.5)

    graph = IdentityGraph()
    for r in [route, prop, far_prop]:
        graph.add_record(r.id, {"source": r.source})

    discover_links([route, prop, far_prop], graph)

    profiles = graph.profiles()
    assert len(profiles) == 1
    assert set(profiles[0]) == {"s1", "p1"}


def test_photo_hash_match():
    r1 = _raw("ph1", "strava", "ath-1", raw_data={"profile_photo_hash": "abc123"})
    r2 = _raw("ph2", "google_reviews", "auth-1", raw_data={"profile_photo_hash": "abc123"})
    r3 = _raw("ph3", "strava", "ath-2", raw_data={"profile_photo_hash": "xyz789"})

    graph = IdentityGraph()
    for r in [r1, r2, r3]:
        graph.add_record(r.id, {"source": r.source})

    discover_links([r1, r2, r3], graph)

    profiles = graph.profiles()
    assert len(profiles) == 1
    assert set(profiles[0]) == {"ph1", "ph2"}


def test_no_links_with_unrelated_records():
    r1 = _raw("x1", "wigle", "net-1", raw_data={"netid": "AA:BB"})
    r2 = _raw("x2", "strava", "seg-1", lat=52.0, lon=0.0)

    graph = IdentityGraph()
    for r in [r1, r2]:
        graph.add_record(r.id, {"source": r.source})

    discover_links([r1, r2], graph)

    assert graph.edge_count == 0
    assert graph.profiles() == []
