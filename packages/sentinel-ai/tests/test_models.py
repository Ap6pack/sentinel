

import uuid

from sqlalchemy import select

from sentinel_ai.models.alert import AlertRecord


async def test_create_alert(db_session):
    alert = AlertRecord(
        id=str(uuid.uuid4()),
        confidence=0.87,
        summary="Test alert",
        reasoning="Test reasoning",
        recommended_action="Take action",
        linked_entity_ids=["entity-1", "entity-2"],
        lat=51.5074,
        lon=-0.1278,
        event_ids=["evt-1", "evt-2"],
    )
    db_session.add(alert)
    await db_session.commit()

    result = await db_session.execute(
        select(AlertRecord).where(AlertRecord.id == alert.id)
    )
    fetched = result.scalar_one()
    assert fetched.confidence == 0.87
    assert fetched.summary == "Test alert"
    assert fetched.linked_entity_ids == ["entity-1", "entity-2"]
    assert fetched.acknowledged is False


async def test_acknowledge_alert(db_session):
    alert = AlertRecord(
        id=str(uuid.uuid4()),
        confidence=0.75,
        summary="Ack test",
        reasoning="r",
        recommended_action="a",
        linked_entity_ids=[],
        event_ids=[],
    )
    db_session.add(alert)
    await db_session.commit()

    alert.acknowledged = True
    await db_session.commit()

    result = await db_session.execute(
        select(AlertRecord).where(AlertRecord.id == alert.id)
    )
    fetched = result.scalar_one()
    assert fetched.acknowledged is True


async def test_alert_nullable_coords(db_session):
    alert = AlertRecord(
        id=str(uuid.uuid4()),
        confidence=0.6,
        summary="No coords",
        reasoning="r",
        recommended_action="a",
        linked_entity_ids=[],
        event_ids=[],
        lat=None,
        lon=None,
    )
    db_session.add(alert)
    await db_session.commit()

    result = await db_session.execute(
        select(AlertRecord).where(AlertRecord.id == alert.id)
    )
    fetched = result.scalar_one()
    assert fetched.lat is None
    assert fetched.lon is None
