# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

import math


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Returns distance in metres between two WGS-84 coordinates."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bbox_contains(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:
    """Check if a point is inside a bounding box. bbox = (min_lat, min_lon, max_lat, max_lon)."""
    return bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3]
