

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_common.bus import BusPublisher

from sentinel_osint.collectors import ALL_COLLECTORS
from sentinel_osint.collectors.base import BaseCollector
from sentinel_osint.linker.builder import build_profile
from sentinel_osint.linker.graph import IdentityGraph
from sentinel_osint.linker.scorer import discover_links
from sentinel_osint.models.profile import ProfileRecord
from sentinel_osint.models.raw import RawRecord
from sentinel_osint.publisher import publish_profile

logger = logging.getLogger(__name__)


@dataclass
class EnrichJob:
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"
    raw_count: int = 0
    profile_count: int = 0
    error: str | None = None


# In-memory job registry (for polling from /api/v1/jobs/{job_id})
_jobs: dict[str, EnrichJob] = {}


def get_job(job_id: str) -> EnrichJob | None:
    return _jobs.get(job_id)


async def run_enrich(
    lat: float,
    lon: float,
    radius_m: float,
    db: AsyncSession,
    bus: BusPublisher | None = None,
) -> EnrichJob:
    """
    Run all available collectors for a bounding box, store raw records,
    run the identity linker, build profiles, persist them, and optionally
    publish to the bus.

    Returns an EnrichJob with results summary.
    """
    job = EnrichJob()
    _jobs[job.job_id] = job
    job.status = "running"

    try:
        # 1. Instantiate and filter available collectors
        collectors: list[BaseCollector] = []
        for cls in ALL_COLLECTORS:
            c = cls()
            if await c.is_available():
                collectors.append(c)
        logger.info(
            "[enrich] %d collectors available for (%.4f, %.4f, %.0fm)",
            len(collectors),
            lat,
            lon,
            radius_m,
        )

        # 2. Run collectors concurrently, gather raw records
        raw_records: list[RawRecord] = []

        async def _run_collector(collector: BaseCollector) -> list[RawRecord]:
            results: list[RawRecord] = []
            try:
                async for record in collector.collect(lat, lon, radius_m):
                    results.append(record)
            except Exception:
                logger.exception("[enrich] collector %s failed", collector.name)
            return results

        tasks = [_run_collector(c) for c in collectors]
        collector_results = await asyncio.gather(*tasks)
        for batch in collector_results:
            raw_records.extend(batch)

        job.raw_count = len(raw_records)
        logger.info("[enrich] collected %d raw records", len(raw_records))

        # 3. Persist raw records
        for rec in raw_records:
            db.add(rec)
        await db.flush()

        # 4. Build identity graph and discover links
        graph = IdentityGraph()
        records_by_id: dict[str, RawRecord] = {}
        for rec in raw_records:
            graph.add_record(rec.id, {"source": rec.source, "source_id": rec.source_id})
            records_by_id[rec.id] = rec

        discover_links(raw_records, graph)

        # 5. Build profiles from connected components
        profiles: list[ProfileRecord] = []
        for component in graph.profiles():
            profile = build_profile(component, records_by_id)
            profiles.append(profile)
            db.add(profile)

        await db.commit()
        job.profile_count = len(profiles)
        logger.info("[enrich] built %d profiles", len(profiles))

        # 6. Publish profiles to the bus
        if bus is not None:
            for profile in profiles:
                await publish_profile(bus, profile)

        job.status = "done"

    except Exception as exc:
        logger.exception("[enrich] job %s failed", job.job_id)
        job.status = "error"
        job.error = str(exc)
        await db.rollback()

    return job
