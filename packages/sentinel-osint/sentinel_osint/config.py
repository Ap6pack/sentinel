

from pydantic_settings import BaseSettings, SettingsConfigDict


class OsintSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SENTINEL_OSINT_", extra="ignore")

    wigle_api_key: str = ""
    strava_token: str = ""
    google_places_api_key: str = ""
    enrich_timeout_s: float = 120.0


osint_settings = OsintSettings()
