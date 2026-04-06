

import uuid

from sqlalchemy import select

from sentinel_osint.models.profile import ProfileRecord
from sentinel_osint.models.raw import RawRecord


async def test_create_and_read_raw_record(db_session):
    rec = RawRecord(
        id=str(uuid.uuid4()),
        source="wigle",
        source_id="AA:BB:CC:DD:EE:01",
        lat=51.5074,
        lon=-0.1278,
        raw_data={"ssid": "TestNet", "channel": 6},
    )
    db_session.add(rec)
    await db_session.commit()

    result = await db_session.execute(select(RawRecord))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].source == "wigle"
    assert rows[0].raw_data["ssid"] == "TestNet"


async def test_create_and_read_profile(db_session):
    profile = ProfileRecord(
        entity_id=f"profile-{uuid.uuid4()}",
        lat=51.5074,
        lon=-0.1278,
        confidence=0.85,
        sources=["wigle", "strava"],
        identifiers={"bssid": "AA:BB:CC:DD:EE:01"},
        attributes={},
        raw_ids=["rec-1", "rec-2"],
    )
    db_session.add(profile)
    await db_session.commit()

    result = await db_session.execute(select(ProfileRecord))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].confidence == 0.85
    assert "wigle" in rows[0].sources
    assert rows[0].raw_ids == ["rec-1", "rec-2"]


async def test_profile_nullable_coords(db_session):
    profile = ProfileRecord(
        entity_id="profile-no-coords",
        lat=None,
        lon=None,
        confidence=0.3,
        sources=["username"],
        identifiers={"username": "jdoe"},
        attributes={},
        raw_ids=["rec-3"],
    )
    db_session.add(profile)
    await db_session.commit()

    result = await db_session.execute(
        select(ProfileRecord).where(ProfileRecord.entity_id == "profile-no-coords")
    )
    p = result.scalar_one()
    assert p.lat is None
    assert p.lon is None


async def test_raw_record_index_fields(db_session):
    """Verify we can query by source and source_id."""
    for i in range(3):
        db_session.add(
            RawRecord(
                id=str(uuid.uuid4()),
                source="wigle" if i < 2 else "strava",
                source_id=f"id-{i}",
                lat=51.0 + i * 0.01,
                lon=-0.1,
                raw_data={},
            )
        )
    await db_session.commit()

    result = await db_session.execute(select(RawRecord).where(RawRecord.source == "wigle"))
    assert len(result.scalars().all()) == 2
