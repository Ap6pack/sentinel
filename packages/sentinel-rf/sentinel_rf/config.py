# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from pydantic_settings import BaseSettings, SettingsConfigDict


class RFSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="SENTINEL_RF_", extra="ignore"
    )

    mock: bool = False
    adsb_device_index: int = 0
    ais_device_index: int = 1
    poll_interval: float = 1.0


rf_settings = RFSettings()
