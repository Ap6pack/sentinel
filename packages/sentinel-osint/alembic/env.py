

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from sentinel_common.config import settings
from sentinel_osint.models.base import Base

# Import models so metadata is populated
from sentinel_osint.models.profile import ProfileRecord  # noqa: F401
from sentinel_osint.models.raw import RawRecord  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_sync_url() -> str:
    """Convert asyncpg URL to psycopg2 for Alembic (sync connections)."""
    return settings.postgres_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def run_migrations_offline() -> None:
    url = get_sync_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_sync_url())
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
