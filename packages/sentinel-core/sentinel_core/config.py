

import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_jwt_secret() -> str:
    """Generate a random secret for dev. Production must set SENTINEL_JWT_SECRET."""
    return secrets.token_hex(32)


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="SENTINEL_", extra="ignore"
    )

    redis_url: str = "redis://localhost:6379"
    jwt_secret: str = _default_jwt_secret()
    admin_username: str = "admin"
    admin_password: str = "admin"
    port: int = 8080
    log_level: str = "INFO"


core_settings = CoreSettings()
