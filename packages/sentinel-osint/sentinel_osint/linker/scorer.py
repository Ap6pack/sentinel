

from __future__ import annotations

import logging

from sentinel_common.geo import haversine_m

from sentinel_osint.linker.graph import IdentityGraph
from sentinel_osint.models.raw import RawRecord

logger = logging.getLogger(__name__)

CONFIDENCE_TABLE: dict[str, float] = {
    "bssid_match": 0.95,
    "spatial_home_cluster": 0.80,
    "username_match": 0.90,
    "name_city_match": 0.60,
    "photo_hash_match": 0.95,
}


def confidence_for_link(reason: str) -> float:
    """Return the default confidence score for a given link reason."""
    return CONFIDENCE_TABLE.get(reason, 0.30)


def discover_links(records: list[RawRecord], graph: IdentityGraph) -> None:
    """
    Examine all record pairs and add edges for discovered identity links.
    Applies the link trigger rules from SKILL-osint.md.
    """
    by_source: dict[str, list[RawRecord]] = {}
    for r in records:
        by_source.setdefault(r.source, []).append(r)

    # BSSID match: same netid across wigle records or between wigle and RF wifi events
    _link_by_field(by_source.get("wigle", []), "netid", "bssid_match", graph)

    # Username match: same source_id across username_* sources
    username_records = [r for r in records if r.source.startswith("username_")]
    _link_by_source_id(username_records, "username_match", graph)

    # Name + city match across google_reviews
    _link_reviews_by_name_city(by_source.get("google_reviews", []), graph)

    # Spatial home cluster: route origin within 50m of property centroid
    _link_spatial(
        by_source.get("strava", []),
        by_source.get("property", []),
        threshold_m=50.0,
        graph=graph,
    )

    # Photo hash match (if raw_data contains profile_photo_hash)
    _link_by_raw_field(records, "profile_photo_hash", "photo_hash_match", graph)


def _link_by_field(records: list[RawRecord], field: str, reason: str, graph: IdentityGraph) -> None:
    """Link records that share the same value for a raw_data field."""
    by_value: dict[str, list[str]] = {}
    for r in records:
        val = r.raw_data.get(field)
        if val:
            by_value.setdefault(str(val), []).append(r.id)
    for ids in by_value.values():
        if len(ids) >= 2:
            conf = confidence_for_link(reason)
            for i in range(len(ids) - 1):
                graph.link(ids[i], ids[i + 1], reason, conf)


def _link_by_source_id(records: list[RawRecord], reason: str, graph: IdentityGraph) -> None:
    """Link records that share the same source_id (e.g. same username across platforms)."""
    by_sid: dict[str, list[str]] = {}
    for r in records:
        by_sid.setdefault(r.source_id, []).append(r.id)
    for ids in by_sid.values():
        if len(ids) >= 2:
            conf = confidence_for_link(reason)
            for i in range(len(ids) - 1):
                graph.link(ids[i], ids[i + 1], reason, conf)


def _link_reviews_by_name_city(records: list[RawRecord], graph: IdentityGraph) -> None:
    """Link google_reviews records with same author_name + city-level proximity."""
    by_name: dict[str, list[RawRecord]] = {}
    for r in records:
        name = r.raw_data.get("author_name", "").strip().lower()
        if name:
            by_name.setdefault(name, []).append(r)
    conf = confidence_for_link("name_city_match")
    for name, recs in by_name.items():
        if len(recs) < 2:
            continue
        for i in range(len(recs) - 1):
            a, b = recs[i], recs[i + 1]
            if a.lat and a.lon and b.lat and b.lon:
                dist = haversine_m(a.lat, a.lon, b.lat, b.lon)
                if dist < 50_000:  # same city ~ 50km
                    graph.link(a.id, b.id, "name_city_match", conf)


def _link_spatial(
    route_records: list[RawRecord],
    property_records: list[RawRecord],
    threshold_m: float,
    graph: IdentityGraph,
) -> None:
    """Link strava route origins within threshold_m of property centroids."""
    conf = confidence_for_link("spatial_home_cluster")
    for route in route_records:
        if route.lat is None or route.lon is None:
            continue
        for prop in property_records:
            if prop.lat is None or prop.lon is None:
                continue
            dist = haversine_m(route.lat, route.lon, prop.lat, prop.lon)
            if dist <= threshold_m:
                graph.link(route.id, prop.id, "spatial_home_cluster", conf)


def _link_by_raw_field(
    records: list[RawRecord], field: str, reason: str, graph: IdentityGraph
) -> None:
    """Link records that share the same value for an arbitrary raw_data field."""
    by_value: dict[str, list[str]] = {}
    for r in records:
        val = r.raw_data.get(field)
        if val:
            by_value.setdefault(str(val), []).append(r.id)
    for ids in by_value.values():
        if len(ids) >= 2:
            conf = confidence_for_link(reason)
            for i in range(len(ids) - 1):
                graph.link(ids[i], ids[i + 1], reason, conf)
