

from enum import StrEnum


class EventKind(StrEnum):
    # Layer 1 -- RF
    AIRCRAFT = "aircraft"
    VESSEL = "vessel"
    WIFI = "wifi"
    BLUETOOTH = "bluetooth"
    PAGER = "pager"
    APRS = "aprs"
    WEATHER_SAT = "weather_sat"

    # Layer 2 -- OSINT
    PROFILE = "profile"
    PROFILE_LINK = "profile_link"

    # Layer 3 -- AI
    ALERT = "alert"
    CORRELATION = "correlation"

    # System
    HEARTBEAT = "heartbeat"
    HEALTH = "health"
