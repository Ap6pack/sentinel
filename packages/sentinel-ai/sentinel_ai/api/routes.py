

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, Query

from sentinel_ai.db import get_db
from sentinel_ai.models.alert import AlertRecord

routes_router = APIRouter()


@routes_router.get("/api/v1/alerts")
async def list_alerts(
    acknowledged: bool = Query(False),
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Returns active alerts. Used by sentinel-viz AlertDrawer."""
    result = await db.execute(
        select(AlertRecord)
        .where(AlertRecord.acknowledged == acknowledged)
        .order_by(AlertRecord.created_at.desc())
        .limit(limit)
    )
    alerts = result.scalars().all()
    return [
        {
            "id": a.id,
            "confidence": a.confidence,
            "summary": a.summary,
            "reasoning": a.reasoning,
            "recommended_action": a.recommended_action,
            "linked_entity_ids": a.linked_entity_ids,
            "lat": a.lat,
            "lon": a.lon,
            "event_ids": a.event_ids,
            "acknowledged": a.acknowledged,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]


@routes_router.post("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark an alert as acknowledged by the operator."""
    result = await db.execute(
        select(AlertRecord).where(AlertRecord.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    return {"id": alert.id, "acknowledged": True}
