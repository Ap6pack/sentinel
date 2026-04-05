# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

import pytest

from sentinel_core.bridge.bus_bridge import BusBridge


def test_matches_filter_no_spec():
    bridge = BusBridge.__new__(BusBridge)
    envelope = {"kind": "aircraft", "lat": 51.5, "lon": -0.1}
    assert bridge._matches_filter(envelope, {}) is True


def test_matches_filter_kind_match():
    bridge = BusBridge.__new__(BusBridge)
    envelope = {"kind": "aircraft", "lat": 51.5, "lon": -0.1}
    spec = {"kinds": ["aircraft", "vessel"]}
    assert bridge._matches_filter(envelope, spec) is True


def test_matches_filter_kind_mismatch():
    bridge = BusBridge.__new__(BusBridge)
    envelope = {"kind": "wifi", "lat": 51.5, "lon": -0.1}
    spec = {"kinds": ["aircraft", "vessel"]}
    assert bridge._matches_filter(envelope, spec) is False


def test_matches_filter_bbox_inside():
    bridge = BusBridge.__new__(BusBridge)
    envelope = {"kind": "aircraft", "lat": 51.5, "lon": -0.1}
    spec = {"bbox": [50.0, -1.0, 52.0, 1.0]}
    assert bridge._matches_filter(envelope, spec) is True


def test_matches_filter_bbox_outside():
    bridge = BusBridge.__new__(BusBridge)
    envelope = {"kind": "aircraft", "lat": 55.0, "lon": -0.1}
    spec = {"bbox": [50.0, -1.0, 52.0, 1.0]}
    assert bridge._matches_filter(envelope, spec) is False


def test_matches_filter_bbox_no_coords():
    """Events without coords should not be filtered out by bbox."""
    bridge = BusBridge.__new__(BusBridge)
    envelope = {"kind": "wifi", "lat": None, "lon": None}
    spec = {"bbox": [50.0, -1.0, 52.0, 1.0]}
    assert bridge._matches_filter(envelope, spec) is True


def test_matches_filter_combined():
    bridge = BusBridge.__new__(BusBridge)
    envelope = {"kind": "aircraft", "lat": 51.5, "lon": -0.1}
    spec = {"kinds": ["aircraft"], "bbox": [50.0, -1.0, 52.0, 1.0]}
    assert bridge._matches_filter(envelope, spec) is True

    # Wrong kind
    envelope2 = {"kind": "wifi", "lat": 51.5, "lon": -0.1}
    assert bridge._matches_filter(envelope2, spec) is False
