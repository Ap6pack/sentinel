

from __future__ import annotations

from ..config import core_settings


def authenticate(username: str, password: str) -> bool:
    """Single-user auth for v1.0 — checks against env-configured credentials."""
    return username == core_settings.admin_username and password == core_settings.admin_password
