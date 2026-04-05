# SKILL: Database — Postgres, SQLAlchemy async, Alembic migrations

## Purpose
Read this before writing any ORM model, query, migration, or database
fixture. Schema ownership, migration workflow, and async SQLAlchemy patterns
are the most common sources of hard-to-recover bugs in SENTINEL. This file
is the authority on all of them.

---

## Database ownership — which module owns which tables

Each module owns its tables exclusively. No module may write to another
module's tables directly — use the REST API or bus.

| Module | Tables owned |
|---|---|
| sentinel-osint | `raw_records`, `profiles` |
| sentinel-ai | `alerts` |
| sentinel-core | `users`, `sessions` |
| sentinel-rf | None (stateless — no persistent tables) |

Shared read-only views (Postgres VIEWs, not tables) may be created by
sentinel-core for the health dashboard — but only sentinel-core creates them,
and they are read-only from all other modules.

---

## SQLAlchemy setup — async only

All database access is async. Never use the synchronous SQLAlchemy API in
production code. The one exception is Alembic migration scripts, which use
synchronous connections because Alembic's `env.py` runs outside the async
event loop.

```python
# packages/sentinel-osint/sentinel_osint/db.py
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sentinel_common.config import settings

engine = create_async_engine(
    settings.postgres_url,           # Must use asyncpg driver:
                                     # postgresql+asyncpg://user:pass@host/db
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,              # Detect stale connections
    echo=False,                      # Set to True for SQL debug logging only
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,          # CRITICAL: prevents lazy-load errors after commit
)
```

`expire_on_commit=False` is non-negotiable in async SQLAlchemy. Without it,
accessing attributes after `session.commit()` triggers a lazy load which
raises `MissingGreenlet` in an async context and is almost impossible to
debug.

---

## Session dependency (FastAPI)

```python
# sentinel_osint/db.py (continued)
from typing import AsyncGenerator
from fastapi import Depends

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Usage in a route:
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sentinel_osint.db import get_db

router = APIRouter()

@router.get("/api/v1/profiles")
async def list_profiles(
    lat: float, lon: float, radius_m: float = 1000,
    db: AsyncSession = Depends(get_db)
):
    ...
```

---

## ORM model conventions

```python
# sentinel_osint/models/base.py
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy import func
from datetime import datetime

class Base(DeclarativeBase):
    pass

# Use mapped_column() with Mapped[] type hints — the modern SQLAlchemy 2.0 style
# Never use Column() with the old 1.x style in new code

# Example:
class ProfileRecord(Base):
    __tablename__ = "profiles"

    entity_id:   Mapped[str]            = mapped_column(primary_key=True)
    lat:         Mapped[float | None]   = mapped_column(nullable=True)
    lon:         Mapped[float | None]   = mapped_column(nullable=True)
    confidence:  Mapped[float]          = mapped_column(default=0.0)
    sources:     Mapped[list]           = mapped_column(type_=JSON)
    identifiers: Mapped[dict]           = mapped_column(type_=JSON)
    attributes:  Mapped[dict]           = mapped_column(type_=JSON)
    raw_ids:     Mapped[list]           = mapped_column(type_=JSON)
    created_at:  Mapped[datetime]       = mapped_column(server_default=func.now())
    updated_at:  Mapped[datetime]       = mapped_column(
                                            server_default=func.now(),
                                            onupdate=func.now()
                                         )
```

Rules:
- Always use `Mapped[T]` type hints with `mapped_column()` — never bare `Column()`
- `server_default=func.now()` for timestamps — not `default=datetime.utcnow`
  (server_default is set by Postgres, not Python, ensuring consistency)
- JSON columns for `list` and `dict` fields — import `JSON` from `sqlalchemy`
- All string primary keys are `uuid4` strings — no integer auto-increment PKs

---

## Writing queries

```python
from sqlalchemy import select, and_
from sentinel_osint.models.profile import ProfileRecord

# SELECT with filter
async def get_profile(db: AsyncSession, entity_id: str) -> ProfileRecord | None:
    result = await db.execute(
        select(ProfileRecord).where(ProfileRecord.entity_id == entity_id)
    )
    return result.scalar_one_or_none()

# SELECT multiple with conditions
async def profiles_near(
    db: AsyncSession, lat: float, lon: float, radius_m: float
) -> list[ProfileRecord]:
    # Simple bounding box — good enough for <10km radius
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
    return list(result.scalars().all())

# INSERT or UPDATE (upsert)
async def upsert_profile(db: AsyncSession, profile: ProfileRecord) -> None:
    existing = await get_profile(db, profile.entity_id)
    if existing:
        existing.confidence = profile.confidence
        existing.sources = profile.sources
        existing.identifiers = profile.identifiers
        existing.updated_at = datetime.utcnow()
    else:
        db.add(profile)
    # Caller's get_db() dependency commits on exit
```

Never use raw SQL strings (`db.execute(text("SELECT ..."))`) for application
queries. Use the ORM or `select()` constructs. Raw SQL is only acceptable in
Alembic migration scripts.

---

## Alembic setup and migration workflow

Alembic manages all schema changes. Never use `Base.metadata.create_all()` in
production code — only in tests with SQLite.

### Initial setup (run once per module that has a database)

```bash
cd packages/sentinel-osint
alembic init alembic
```

Edit `alembic/env.py`:

```python
# alembic/env.py — key sections only
from sentinel_osint.models.base import Base
from sentinel_common.config import settings
import re

# Convert asyncpg URL to psycopg2 for Alembic (Alembic uses sync connections)
def get_sync_url():
    return settings.postgres_url.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )

target_metadata = Base.metadata

def run_migrations_online():
    connectable = create_engine(get_sync_url())
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,       # Detect column type changes
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()
```

### Creating a migration

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "add profiles table"

# Always review the generated migration before applying:
cat alembic/versions/xxxx_add_profiles_table.py
```

**Always review auto-generated migrations.** Alembic often misses:
- Index creation on JSON columns
- Custom Postgres types (if any)
- Data migrations (auto-generate only handles schema, not data)

### Applying migrations

```bash
# Upgrade to latest
alembic upgrade head

# Check current version
alembic current

# Downgrade one step (for rollback)
alembic downgrade -1
```

### Migration in Docker

The sentinel-core Docker entrypoint runs migrations before starting the server:

```dockerfile
# packages/sentinel-core/Dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn sentinel_core.app:app --host 0.0.0.0 --port 8080"]
```

Each module with a database runs its own migrations on startup. Migrations
are idempotent — running them twice is safe.

---

## Schema change rules

| Change | Safe to deploy? | Migration needed? |
|---|---|---|
| Add nullable column | Yes | Yes |
| Add non-nullable column with default | Yes | Yes |
| Add non-nullable column without default | No — add with default first | Yes |
| Add index | Yes (use CONCURRENTLY in prod) | Yes |
| Rename column | No — add new, migrate data, drop old | Yes (3-step) |
| Drop column | No — make nullable first, then drop | Yes (2-step) |
| Change column type | No — add new column, migrate, drop old | Yes (3-step) |

**Never rename or drop a column in a single migration.** Always use the
multi-step pattern to avoid downtime.

### 3-step column rename example

```python
# Step 1: Add new column (deploy with both old and new code reading both columns)
op.add_column("profiles", sa.Column("entity_key", sa.String()))
op.execute("UPDATE profiles SET entity_key = entity_id")

# Step 2: (next deploy) Remove references to old column from code

# Step 3: (next deploy) Drop old column
op.drop_column("profiles", "entity_id")
```

---

## Postgres connection string format

```
# Async (application code) — asyncpg driver
postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel

# Sync (Alembic only) — psycopg2 driver
postgresql+psycopg2://sentinel:sentinel@localhost:5432/sentinel

# In-memory SQLite (tests only)
sqlite+aiosqlite:///:memory:
```

The `SENTINEL_POSTGRES_URL` env var always uses the asyncpg format.
Alembic's `env.py` converts it to psycopg2 format at runtime (see above).

---

## Docker Postgres setup

```yaml
# infra/docker-compose.yml
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: sentinel
      POSTGRES_USER: sentinel
      POSTGRES_PASSWORD: sentinel
    ports: ["5432:5432"]
    volumes:
      - ${PGDATA_PATH:-./pgdata}:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sentinel"]
      interval: 5s
      timeout: 3s
      retries: 10
    profiles: ["history", "full"]
```

Note: Postgres is only started with the `history` or `full` profile.
The `basic` profile uses no persistent storage — RF and OSINT data is lost
on restart. This is intentional for development.

---

## Common mistakes to avoid

- **Do not** use `Base.metadata.create_all()` in application startup code —
  only Alembic manages the production schema
- **Do not** use `expire_on_commit=True` (the SQLAlchemy default) — it causes
  `MissingGreenlet` errors in async code after commit
- **Do not** use `session.execute(text("raw SQL"))` for application queries —
  only in Alembic migrations
- **Do not** access ORM relationships lazily — use `selectinload()` or
  `joinedload()` explicitly in queries that need related objects
- **Do not** share a single `AsyncSession` across concurrent coroutines —
  sessions are not thread-safe; create a new session per request via `get_db()`
- **Do not** write to another module's tables — use the REST API
- **Do not** commit inside a route handler — let the `get_db()` dependency
  handle commit/rollback on exit
- **Do not** add a non-nullable column without a default in a single migration —
  it will fail on tables with existing rows
