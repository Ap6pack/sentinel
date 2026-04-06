

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinel_ai.models.alert import AlertRecord
from sentinel_ai.models.base import Base


@pytest.fixture
async def app_with_db():
    """Create app with SQLite-backed DB dependency override."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from sentinel_ai.app import app
    from sentinel_ai.db import get_db

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    yield app, factory
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_health_endpoint():
    from sentinel_ai.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["module"] == "sentinel-ai"
    assert data["status"] == "ok"
    assert "max_calls_per_hour" in data


async def test_list_alerts_empty(app_with_db):
    app, _ = app_with_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/v1/alerts")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_alerts_with_data(app_with_db):
    app, factory = app_with_db

    # Insert an alert directly
    async with factory() as session:
        alert = AlertRecord(
            id=str(uuid.uuid4()),
            confidence=0.87,
            summary="Test alert",
            reasoning="Test reasoning",
            recommended_action="Take action",
            linked_entity_ids=["e1"],
            lat=51.5,
            lon=-0.1,
            event_ids=["evt-1"],
        )
        session.add(alert)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/v1/alerts?acknowledged=false")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["confidence"] == 0.87


async def test_acknowledge_alert(app_with_db):
    app, factory = app_with_db

    alert_id = str(uuid.uuid4())
    async with factory() as session:
        alert = AlertRecord(
            id=alert_id,
            confidence=0.75,
            summary="Ack test",
            reasoning="r",
            recommended_action="a",
            linked_entity_ids=[],
            event_ids=[],
        )
        session.add(alert)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(f"/api/v1/alerts/{alert_id}/acknowledge")
    assert resp.status_code == 200
    assert resp.json()["acknowledged"] is True


async def test_acknowledge_alert_not_found(app_with_db):
    app, _ = app_with_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(f"/api/v1/alerts/{uuid.uuid4()}/acknowledge")
    assert resp.status_code == 404
