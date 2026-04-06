

from __future__ import annotations

import uuid

from sentinel_osint.models.profile import ProfileRecord
from sentinel_osint.models.raw import RawRecord

SOURCE_PRIORITY = {"property": 4, "wigle": 3, "strava": 2, "google_reviews": 1}


def build_profile(component: list[str], records: dict[str, RawRecord]) -> ProfileRecord:
    """
    Given a connected component of record IDs and a dict of RawRecords,
    assemble a ProfileRecord with the best available coordinate and
    merged identifiers.
    """
    recs = [records[rid] for rid in component if rid in records]
    best = sorted(recs, key=lambda r: SOURCE_PRIORITY.get(r.source, 0), reverse=True)
    lat = next((r.lat for r in best if r.lat is not None), None)
    lon = next((r.lon for r in best if r.lon is not None), None)

    identifiers: dict[str, str] = {}
    for r in recs:
        if r.source == "strava":
            identifiers["strava_id"] = r.source_id
        elif r.source == "wigle":
            identifiers["bssid"] = r.source_id
            identifiers["ssid"] = r.raw_data.get("ssid", "")

    return ProfileRecord(
        entity_id=f"profile-{uuid.uuid4()}",
        lat=lat,
        lon=lon,
        confidence=min(0.99, len(recs) * 0.2),
        sources=list({r.source for r in recs}),
        identifiers=identifiers,
        attributes={},
        raw_ids=component,
    )
