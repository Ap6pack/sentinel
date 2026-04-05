# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_core.app import app
from sentinel_core.auth.tokens import issue_token


@pytest.fixture
def token():
    return issue_token("admin")


async def test_login_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["username"] == "admin"


async def test_login_failure():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
    assert resp.status_code == 401


async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "modules" in data
    assert "overall" in data


async def test_proxy_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/rf/api/v1/health")
    assert resp.status_code == 401


async def test_proxy_with_valid_token(token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get(
            "/api/rf/api/v1/health",
            headers={"Authorization": f"Bearer {token}"},
        )
    # 502 or connection error is expected (no RF module running) — not 401
    assert resp.status_code != 401
