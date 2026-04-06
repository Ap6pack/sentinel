

import json
from pathlib import Path

import httpx
import pytest

from sentinel_osint.collectors.wigle import WiGLECollector

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def wigle_response():
    return json.loads((FIXTURES / "wigle_response.json").read_text())


@pytest.fixture
def collector(monkeypatch):
    c = WiGLECollector()
    monkeypatch.setattr(c, "_api_key", "test-key-123")
    return c


async def test_collect_yields_raw_records(collector, httpx_mock, wigle_response):
    httpx_mock.add_response(json=wigle_response)

    records = []
    async for rec in collector.collect(lat=51.5074, lon=-0.1278, radius_m=500):
        records.append(rec)

    assert len(records) == 3
    assert records[0].source == "wigle"
    assert records[0].source_id == "AA:BB:CC:DD:EE:01"
    assert records[0].lat == 51.5074
    assert records[0].lon == -0.1278
    assert records[0].raw_data["ssid"] == "HomeNet_Smith"


async def test_collect_no_api_key(monkeypatch):
    c = WiGLECollector()
    monkeypatch.setattr(c, "_api_key", "")

    records = []
    async for rec in c.collect(lat=51.5, lon=-0.1, radius_m=500):
        records.append(rec)

    assert len(records) == 0


async def test_collect_handles_429(collector, httpx_mock):
    httpx_mock.add_response(
        status_code=429,
        headers={"Retry-After": "30"},
    )

    records = []
    async for rec in collector.collect(lat=51.5, lon=-0.1, radius_m=500):
        records.append(rec)

    assert len(records) == 0


async def test_collect_handles_timeout(collector, httpx_mock):
    httpx_mock.add_exception(httpx.ReadTimeout("timeout"))

    records = []
    async for rec in collector.collect(lat=51.5, lon=-0.1, radius_m=500):
        records.append(rec)

    assert len(records) == 0


async def test_collect_handles_server_error(collector, httpx_mock):
    httpx_mock.add_response(status_code=500)

    records = []
    async for rec in collector.collect(lat=51.5, lon=-0.1, radius_m=500):
        records.append(rec)

    assert len(records) == 0


async def test_is_available_with_key(collector):
    assert await collector.is_available() is True


async def test_is_available_without_key(monkeypatch):
    c = WiGLECollector()
    monkeypatch.setattr(c, "_api_key", "")
    assert await c.is_available() is False
