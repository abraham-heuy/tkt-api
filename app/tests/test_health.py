
"""Health endpoint tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_returns_200(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"

