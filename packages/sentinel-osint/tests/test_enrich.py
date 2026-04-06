

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from sentinel_osint.enrich import get_job, run_enrich
from sentinel_osint.models.profile import ProfileRecord
from sentinel_osint.models.raw import RawRecord


def _make_wigle_record(netid: str, lat: float, lon: float) -> RawRecord:
    return RawRecord(
        id=str(uuid.uuid4()),
        source="wigle",
        source_id=netid,
        lat=lat,
        lon=lon,
        raw_data={"netid": netid, "ssid": f"Net_{netid[:4]}"},
    )


class FakeCollector:
    """Fake collector that yields pre-built records."""

    name = "fake"

    def __init__(self, records: list[RawRecord]) -> None:
        self._records = records

    async def is_available(self) -> bool:
        return True

    async def collect(self, lat, lon, radius_m):
        for r in self._records:
            yield r


async def test_enrich_creates_profiles(db_session):
    """When two records share a BSSID, enrich should link them into a profile."""
    r1 = _make_wigle_record("AA:BB:CC", 51.50, -0.10)
    r2 = _make_wigle_record("AA:BB:CC", 51.501, -0.101)
    r3 = _make_wigle_record("DD:EE:FF", 51.60, -0.20)

    fake_collectors = [
        type(
            "C",
            (),
            {
                "__init__": lambda self: None,
                "is_available": AsyncMock(return_value=True),
                "collect": lambda self, lat, lon, radius_m: _async_gen([r1, r2, r3]),
                "name": "fake",
            },
        )
    ]

    with patch("sentinel_osint.enrich.ALL_COLLECTORS", fake_collectors):
        job = await run_enrich(51.5, -0.1, 500, db_session, bus=None)

    assert job.status == "done"
    assert job.raw_count == 3

    # Should have created 1 profile (r1+r2 linked by bssid_match)
    result = await db_session.execute(select(ProfileRecord))
    profiles = result.scalars().all()
    assert len(profiles) == 1
    assert job.profile_count == 1

    profile = profiles[0]
    assert profile.entity_id.startswith("profile-")
    assert len(profile.raw_ids) == 2
    assert "wigle" in profile.sources


async def test_enrich_no_links_no_profiles(db_session):
    """Records with no linkable identifiers produce no profiles."""
    r1 = _make_wigle_record("AA:BB:CC", 51.50, -0.10)
    r2 = _make_wigle_record("DD:EE:FF", 51.60, -0.20)

    fake_collectors = [
        type(
            "C",
            (),
            {
                "__init__": lambda self: None,
                "is_available": AsyncMock(return_value=True),
                "collect": lambda self, lat, lon, radius_m: _async_gen([r1, r2]),
                "name": "fake",
            },
        )
    ]

    with patch("sentinel_osint.enrich.ALL_COLLECTORS", fake_collectors):
        job = await run_enrich(51.5, -0.1, 500, db_session, bus=None)

    assert job.status == "done"
    assert job.raw_count == 2
    assert job.profile_count == 0


async def test_enrich_job_registry(db_session):
    """Job should be retrievable by ID."""
    fake_collectors = [
        type(
            "C",
            (),
            {
                "__init__": lambda self: None,
                "is_available": AsyncMock(return_value=True),
                "collect": lambda self, lat, lon, radius_m: _async_gen([]),
                "name": "fake",
            },
        )
    ]

    with patch("sentinel_osint.enrich.ALL_COLLECTORS", fake_collectors):
        job = await run_enrich(51.5, -0.1, 500, db_session, bus=None)

    retrieved = get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.status == "done"


async def test_enrich_publishes_to_bus(db_session):
    """When a bus is provided, profiles should be published."""
    r1 = _make_wigle_record("AA:BB:CC", 51.50, -0.10)
    r2 = _make_wigle_record("AA:BB:CC", 51.501, -0.101)

    fake_collectors = [
        type(
            "C",
            (),
            {
                "__init__": lambda self: None,
                "is_available": AsyncMock(return_value=True),
                "collect": lambda self, lat, lon, radius_m: _async_gen([r1, r2]),
                "name": "fake",
            },
        )
    ]

    mock_bus = AsyncMock()
    mock_bus.publish = AsyncMock(return_value="msg-123")

    with patch("sentinel_osint.enrich.ALL_COLLECTORS", fake_collectors):
        job = await run_enrich(51.5, -0.1, 500, db_session, bus=mock_bus)

    assert job.profile_count == 1
    mock_bus.publish.assert_called_once()


async def _async_gen(items):
    for item in items:
        yield item
