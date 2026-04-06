

from __future__ import annotations

import logging

from sentinel_common.envelope import EventEnvelope

logger = logging.getLogger(__name__)


def match_identifiers(
    events: list[EventEnvelope],
    profiles: list[dict],
) -> list[tuple[EventEnvelope, dict, str, float]]:
    """
    Match events against profiles by BSSID or SSID identifiers.

    Returns a list of (event, profile, reason, confidence) tuples for each
    match found.
    """
    matches: list[tuple[EventEnvelope, dict, str, float]] = []

    # Build lookup indexes from profiles
    bssid_index: dict[str, dict] = {}
    ssid_index: dict[str, dict] = {}
    for profile in profiles:
        identifiers = profile.get("identifiers", {})
        bssid = identifiers.get("bssid")
        if bssid:
            bssid_index[bssid.upper()] = profile
        ssid = identifiers.get("ssid")
        if ssid:
            ssid_index[ssid.lower()] = profile

    for event in events:
        if event.kind != "wifi":
            continue

        payload = event.payload
        event_bssid = payload.get("bssid", "").upper()
        event_ssid = payload.get("ssid", "").lower()

        # BSSID match — high confidence
        if event_bssid and event_bssid in bssid_index:
            matches.append(
                (event, bssid_index[event_bssid], "bssid_match", 0.90)
            )
            logger.info(
                "[identifier] BSSID match %s -> %s",
                event_bssid,
                bssid_index[event_bssid].get("entity_id"),
            )
            continue  # BSSID match is sufficient, skip SSID

        # SSID match — lower confidence
        if event_ssid and event_ssid in ssid_index:
            matches.append(
                (event, ssid_index[event_ssid], "ssid_match", 0.55)
            )
            logger.info(
                "[identifier] SSID match %s -> %s",
                event_ssid,
                ssid_index[event_ssid].get("entity_id"),
            )

    return matches
