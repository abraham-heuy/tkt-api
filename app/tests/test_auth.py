
"""Auth endpoint tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_check_email_exists(
    client: AsyncClient, manager_user
):
    resp = await client.post(
        "/auth/check-email",
        json={"email": "manager@test.com"},
    )
    assert resp.status_code == 200
    assert resp.json()["exists"] is True


@pytest.mark.asyncio
async def test_check_email_not_found(client: AsyncClient):
    resp = await client.post(
        "/auth/check-email",
        json={"email": "nobody@test.com"},
    )
    assert resp.status_code == 200
    assert resp.json()["exists"] is False


@pytest.mark.asyncio
async def test_admin_login_success(
    client: AsyncClient, manager_user
):
    resp = await client.post(
        "/auth/login",
        json={"email": "manager@test.com", "pin": "1234"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_admin_login_wrong_pin(
    client: AsyncClient, manager_user
):
    resp = await client.post(
        "/auth/login",
        json={"email": "manager@test.com", "pin": "0000"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookies(client: AsyncClient):
    resp = await client.post("/auth/logout")
    assert resp.status_code == 204

