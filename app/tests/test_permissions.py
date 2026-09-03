
"""Permission endpoint tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_services(
    client: AsyncClient, admin_headers
):
    resp = await client.get(
        "/permissions/services", headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 6
    names = [s["name"] for s in data]
    assert "tickets" in names
    assert "analytics" in names
    assert "user_management" in names


@pytest.mark.asyncio
async def test_get_manager_permissions_empty(
    client: AsyncClient, admin_headers, manager_user
):
    resp = await client.get(
        f"/permissions/users/{manager_user.id}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["permissions"] == []


@pytest.mark.asyncio
async def test_grant_permissions(
    client: AsyncClient, admin_headers, manager_user
):
    # get the tickets:read action_group id
    svc_resp = await client.get(
        "/permissions/services", headers=admin_headers
    )
    services = svc_resp.json()
    tickets_svc = next(
        s for s in services if s["name"] == "tickets"
    )
    read_action = next(
        a for a in tickets_svc["actions"]
        if a["action"] == "read"
    )

    resp = await client.post(
        f"/permissions/users/{manager_user.id}",
        json={"action_group_ids": [read_action["id"]]},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    perms = resp.json()["permissions"]
    assert len(perms) >= 1
    assert any(
        p["service_group"] == "tickets"
        and p["action"] == "read"
        for p in perms
    )


@pytest.mark.asyncio
async def test_client_cannot_access_permissions(
    client: AsyncClient, client_headers
):
    resp = await client.get(
        "/permissions/services", headers=client_headers
    )
    assert resp.status_code == 403

