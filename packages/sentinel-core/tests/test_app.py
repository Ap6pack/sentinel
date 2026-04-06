

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


async def test_proxy_osint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/osint/api/v1/health")
    assert resp.status_code == 401


async def test_proxy_osint_with_valid_token(token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get(
            "/api/osint/api/v1/health",
            headers={"Authorization": f"Bearer {token}"},
        )
    # 502 expected (no osint module running locally) — but not 401
    assert resp.status_code != 401


async def test_proxy_osint_profiles_with_auth(token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get(
            "/api/osint/api/v1/profiles?lat=51.5&lon=-0.1&radius_m=1000",
            headers={"Authorization": f"Bearer {token}"},
        )
    # 502 expected (no osint module running) — confirms proxy routes correctly
    assert resp.status_code != 401
