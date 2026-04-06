

from pydantic_settings import BaseSettings, SettingsConfigDict


class SentinelSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="SENTINEL_", extra="ignore"
    )

    redis_url: str = "redis://localhost:6379"
    postgres_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel"
    log_level: str = "INFO"
    default_lat: float = 51.5074
    default_lon: float = -0.1278


settings = SentinelSettings()
