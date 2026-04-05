# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from __future__ import annotations

import time

import jwt

from ..config import core_settings

ALGORITHM = "HS256"
TTL_SECONDS = 3600 * 8  # 8-hour sessions


def issue_token(username: str) -> str:
    """Issue a JWT for the given username."""
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + TTL_SECONDS,
    }
    return jwt.encode(payload, core_settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify and decode a JWT. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, core_settings.jwt_secret, algorithms=[ALGORITHM])
