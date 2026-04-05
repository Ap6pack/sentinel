# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer

from .tokens import verify_token

bearer = HTTPBearer(auto_error=False)


async def require_auth(request: Request) -> None:
    """FastAPI dependency — rejects requests without a valid JWT."""
    creds = await bearer(request)
    if not creds:
        raise HTTPException(401, "Missing token")
    try:
        payload = verify_token(creds.credentials)
        request.state.user = payload["sub"]
    except Exception:
        raise HTTPException(401, "Invalid token")
