
"""User + profile endpoint tests."""

import pytest
from httpx import AsyncClient


# ── Admin: list users ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users(
    client: AsyncClient, admin_headers, client_user
):
    resp = await client.get(
        "/users", headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_list_users_filter_by_role(
    client: AsyncClient, admin_headers, client_user
):
    resp = await client.get(
        "/users?role=client", headers=admin_headers
    )
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["user"]["role"] == "client"


# ── Admin: get single user ──────────────────────────────────────


@pytest.mark.asyncio
async def test_get_user_with_profile(
    client: AsyncClient, admin_headers, client_user
):
    resp = await client.get(
        f"/users/{client_user.id}", headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["email"] == "client@test.com"
    assert data["profile"]["full_name"] == "Test Client"


# ── Admin: update user ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_user_profile(
    client: AsyncClient, admin_headers, client_user
):
    resp = await client.put(
        f"/users/{client_user.id}",
        json={
            "full_name": "Updated Client",
            "connection_area": "Westlands",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile"]["full_name"] == "Updated Client"
    assert data["profile"]["connection_area"] == "Westlands"


# ── Admin: deactivate user ──────────────────────────────────────


@pytest.mark.asyncio
async def test_deactivate_user(
    client: AsyncClient, admin_headers, client_user
):
    resp = await client.delete(
        f"/users/{client_user.id}", headers=admin_headers
    )
    assert resp.status_code == 204


# ── Client: profile/me ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_my_profile(
    client: AsyncClient, client_headers
):
    resp = await client.get(
        "/profile/me", headers=client_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["email"] == "client@test.com"
    assert data["profile"] is not None


@pytest.mark.asyncio
async def test_update_my_profile(
    client: AsyncClient, client_headers
):
    resp = await client.put(
        "/profile/me",
        json={"phone": "+254711111111"},
        headers=client_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["profile"]["phone"] == "+254711111111"


# ── Access control ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_cannot_list_users(
    client: AsyncClient, client_headers
):
    resp = await client.get(
        "/users", headers=client_headers
    )
    assert resp.status_code == 403

