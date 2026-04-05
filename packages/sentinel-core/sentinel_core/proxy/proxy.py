# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request, Response

router = APIRouter()

MODULE_ROUTES: dict[str, str] = {
    "rf": "http://localhost:5050",
    "osint": "http://localhost:5001",
    "ai": "http://localhost:5002",
}


@router.api_route(
    "/api/{module}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"]
)
async def proxy(request: Request, module: str, path: str) -> Response:
    """Reverse proxy — routes /api/{module}/... to the target module."""
    target = MODULE_ROUTES.get(module)
    if not target:
        return Response(status_code=404, content="Unknown module")
    url = f"{target}/{path}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                headers={
                    k: v for k, v in request.headers.items() if k.lower() != "host"
                },
                content=await request.body(),
                params=dict(request.query_params),
            )
    except httpx.ConnectError:
        return Response(status_code=502, content=f"Module {module} unreachable")
    except httpx.TimeoutException:
        return Response(status_code=504, content=f"Module {module} timeout")
    # Filter out hop-by-hop headers
    excluded = {"transfer-encoding", "connection", "keep-alive"}
    headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=headers,
    )
