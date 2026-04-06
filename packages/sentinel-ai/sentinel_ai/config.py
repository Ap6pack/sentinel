

from __future__ import annotations

import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_jwt_secret() -> str:
    return secrets.token_hex(32)


class AiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SENTINEL_AI_", extra="ignore")

    port: int = 5002
    log_level: str = "INFO"
    redis_url: str = "redis://localhost:6379"
    postgres_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel"
    jwt_secret: str = ""
    anthropic_api_key: str = ""
    max_calls_per_hour: int = 100
    osint_api_url: str = "http://localhost:5001"
    spatial_radius_m: float = 150.0


ai_settings = AiSettings()
