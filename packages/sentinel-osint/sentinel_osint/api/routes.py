

from __future__ import annotations

import asyncio

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, Query

from sentinel_osint.db import AsyncSessionLocal, get_db
from sentinel_osint.enrich import EnrichJob, get_job, run_enrich
from sentinel_osint.models.profile import ProfileRecord
from sentinel_osint.models.raw import RawRecord

routes_router = APIRouter()


@routes_router.get("/api/v1/profiles")
async def list_profiles(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: float = Query(1000),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return profiles within radius_m of lat/lon."""
    deg = radius_m / 111_000
    result = await db.execute(
        select(ProfileRecord).where(
            and_(
                ProfileRecord.lat.between(lat - deg, lat + deg),
                ProfileRecord.lon.between(lon - deg, lon + deg),
                ProfileRecord.lat.isnot(None),
                ProfileRecord.lon.isnot(None),
            )
        )
    )
    profiles = result.scalars().all()
    return [
        {
            "entity_id": p.entity_id,
            "lat": p.lat,
            "lon": p.lon,
            "confidence": p.confidence,
            "sources": p.sources,
            "identifiers": p.identifiers,
        }
        for p in profiles
    ]


@routes_router.post("/api/v1/enrich")
async def trigger_enrich(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: float = Query(500),
) -> dict:
    """
    Trigger all collectors for the given area, run the linker, build profiles.
    Returns immediately with a job_id; poll /api/v1/jobs/{job_id} for status.
    """
    from sentinel_osint.app import bus
    from sentinel_osint.enrich import _jobs

    job = EnrichJob()
    _jobs[job.job_id] = job

    asyncio.create_task(_run_enrich_background(job, lat, lon, radius_m, bus))
    return {"job_id": job.job_id, "status": job.status}


async def _run_enrich_background(
    job: EnrichJob,
    lat: float,
    lon: float,
    radius_m: float,
    bus: object,
) -> None:
    """Background task that runs enrichment with its own DB session."""
    job.status = "running"
    async with AsyncSessionLocal() as db:
        result = await run_enrich(lat, lon, radius_m, db, bus)
        job.status = result.status
        job.raw_count = result.raw_count
        job.profile_count = result.profile_count
        job.error = result.error


@routes_router.get("/api/v1/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict:
    """Poll enrichment job status."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "raw_count": job.raw_count,
        "profile_count": job.profile_count,
        "error": job.error,
    }


@routes_router.get("/api/v1/graph/{entity_id}")
async def get_graph(
    entity_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the identity graph neighbourhood for a profile."""
    result = await db.execute(select(ProfileRecord).where(ProfileRecord.entity_id == entity_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Fetch the raw records that compose this profile
    raw_ids = profile.raw_ids or []
    raw_result = await db.execute(select(RawRecord).where(RawRecord.id.in_(raw_ids)))
    raw_records = raw_result.scalars().all()

    return {
        "entity_id": profile.entity_id,
        "confidence": profile.confidence,
        "sources": profile.sources,
        "identifiers": profile.identifiers,
        "records": [
            {
                "id": r.id,
                "source": r.source,
                "source_id": r.source_id,
                "lat": r.lat,
                "lon": r.lon,
            }
            for r in raw_records
        ],
    }
