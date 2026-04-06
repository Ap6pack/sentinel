

import math

from sentinel_common.geo import bbox_contains, haversine_m


def test_haversine_same_point():
    assert haversine_m(51.5, -0.1, 51.5, -0.1) == 0.0


def test_haversine_known_distance():
    # London to Paris ~341 km
    dist = haversine_m(51.5074, -0.1278, 48.8566, 2.3522)
    assert 340_000 < dist < 345_000


def test_haversine_antipodal():
    # North pole to south pole ~20,015 km
    dist = haversine_m(90.0, 0.0, -90.0, 0.0)
    expected = math.pi * 6_371_000
    assert abs(dist - expected) < 100  # within 100m


def test_bbox_contains_inside():
    bbox = (50.0, -1.0, 52.0, 1.0)
    assert bbox_contains(51.0, 0.0, bbox) is True


def test_bbox_contains_outside():
    bbox = (50.0, -1.0, 52.0, 1.0)
    assert bbox_contains(53.0, 0.0, bbox) is False


def test_bbox_contains_on_edge():
    bbox = (50.0, -1.0, 52.0, 1.0)
    assert bbox_contains(50.0, -1.0, bbox) is True
    assert bbox_contains(52.0, 1.0, bbox) is True
