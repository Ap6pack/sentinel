

from sentinel_osint.linker.graph import IdentityGraph
from sentinel_osint.linker.scorer import confidence_for_link


def test_link_creates_edge():
    g = IdentityGraph()
    g.add_record("a", {"source": "wigle"})
    g.add_record("b", {"source": "strava"})
    g.link("a", "b", reason="bssid_match", confidence=0.95)
    assert g.edge_count == 1


def test_link_strengthens_existing():
    g = IdentityGraph()
    g.add_record("a", {})
    g.add_record("b", {})
    g.link("a", "b", reason="name_city_match", confidence=0.60)
    g.link("a", "b", reason="bssid_match", confidence=0.95)
    # Should take max confidence
    assert g._g["a"]["b"]["confidence"] == 0.95


def test_link_below_threshold_ignored():
    g = IdentityGraph()
    g.add_record("a", {})
    g.add_record("b", {})
    g.link("a", "b", reason="weak", confidence=0.10)
    assert g.edge_count == 0


def test_profiles_returns_connected_components():
    g = IdentityGraph()
    g.add_record("a", {})
    g.add_record("b", {})
    g.add_record("c", {})
    g.add_record("d", {})
    g.link("a", "b", reason="bssid_match", confidence=0.95)
    g.link("b", "c", reason="username_match", confidence=0.90)
    # d is isolated

    profiles = g.profiles()
    assert len(profiles) == 1
    assert set(profiles[0]) == {"a", "b", "c"}


def test_profiles_multiple_components():
    g = IdentityGraph()
    for n in ["a", "b", "c", "d"]:
        g.add_record(n, {})
    g.link("a", "b", reason="bssid_match", confidence=0.95)
    g.link("c", "d", reason="username_match", confidence=0.90)

    profiles = g.profiles()
    assert len(profiles) == 2


def test_single_node_not_a_profile():
    g = IdentityGraph()
    g.add_record("alone", {})
    assert g.profiles() == []


def test_scorer_known_reasons():
    assert confidence_for_link("bssid_match") == 0.95
    assert confidence_for_link("spatial_home_cluster") == 0.80
    assert confidence_for_link("username_match") == 0.90
    assert confidence_for_link("name_city_match") == 0.60
    assert confidence_for_link("photo_hash_match") == 0.95


def test_scorer_unknown_reason():
    assert confidence_for_link("unknown_reason") == 0.30
