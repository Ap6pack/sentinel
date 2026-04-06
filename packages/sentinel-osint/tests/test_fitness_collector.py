

import pytest

from sentinel_osint.collectors.fitness import FitnessCollector, infer_home_coord


@pytest.fixture
def collector(monkeypatch):
    c = FitnessCollector()
    monkeypatch.setattr(c, "_token", "test-token-123")
    return c


async def test_collect_yields_segments(collector, httpx_mock):
    httpx_mock.add_response(
        json={
            "segments": [
                {
                    "id": 12345,
                    "name": "Morning Run",
                    "start_latlng": [51.5074, -0.1278],
                    "end_latlng": [51.51, -0.12],
                },
                {
                    "id": 12346,
                    "name": "Park Loop",
                    "start_latlng": [51.508, -0.126],
                    "end_latlng": [51.509, -0.125],
                },
            ]
        }
    )

    records = []
    async for rec in collector.collect(lat=51.5074, lon=-0.1278, radius_m=500):
        records.append(rec)

    assert len(records) == 2
    assert records[0].source == "strava"
    assert records[0].source_id == "12345"
    assert records[0].lat == 51.5074
    assert records[0].lon == -0.1278


async def test_collect_no_token(monkeypatch):
    c = FitnessCollector()
    monkeypatch.setattr(c, "_token", "")

    records = []
    async for rec in c.collect(lat=51.5, lon=-0.1, radius_m=500):
        records.append(rec)

    assert len(records) == 0


async def test_collect_handles_429(collector, httpx_mock):
    httpx_mock.add_response(status_code=429, headers={"Retry-After": "30"})

    records = []
    async for rec in collector.collect(lat=51.5, lon=-0.1, radius_m=500):
        records.append(rec)

    assert len(records) == 0


async def test_collect_handles_timeout(collector, httpx_mock):
    import httpx

    httpx_mock.add_exception(httpx.ReadTimeout("timeout"))

    records = []
    async for rec in collector.collect(lat=51.5, lon=-0.1, radius_m=500):
        records.append(rec)

    assert len(records) == 0


async def test_is_available_with_token(collector):
    assert await collector.is_available() is True


async def test_is_available_without_token(monkeypatch):
    c = FitnessCollector()
    monkeypatch.setattr(c, "_token", "")
    assert await c.is_available() is False


def test_infer_home_coord_with_clear_cluster():
    # Cluster of points near (51.5, -0.1)
    route_starts = [
        (51.500, -0.100),
        (51.5005, -0.1005),
        (51.5001, -0.0998),
        # Outlier
        (52.0, 0.5),
    ]
    result = infer_home_coord(route_starts)
    assert result is not None
    lat, lon = result
    assert abs(lat - 51.5002) < 0.005
    assert abs(lon - (-0.1001)) < 0.005


def test_infer_home_coord_too_few_routes():
    assert infer_home_coord([(51.5, -0.1), (51.6, -0.2)]) is None


def test_infer_home_coord_no_cluster():
    # All points far apart — no cluster should form
    result = infer_home_coord(
        [
            (51.5, -0.1),
            (52.5, 1.0),
            (53.5, 2.0),
        ]
    )
    assert result is None
