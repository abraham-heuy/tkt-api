
"""Ticket endpoint tests — client + admin flows."""

import pytest
from httpx import AsyncClient


TICKET_PAYLOAD = {
    "subject": "Internet keeps dropping",
    "description": "Connection drops every 30 minutes since Monday",
    "category": "connectivity",
}


# ── Client creates a ticket ──────────────────────────────────────


@pytest.mark.asyncio
async def test_create_ticket(
    client: AsyncClient, client_headers
):
    resp = await client.post(
        "/tickets",
        json=TICKET_PAYLOAD,
        headers=client_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["subject"] == TICKET_PAYLOAD["subject"]
    assert data["status"] == "pending"
    assert data["assigned_to"] is None


@pytest.mark.asyncio
async def test_create_ticket_unauthenticated(
    client: AsyncClient,
):
    resp = await client.post("/tickets", json=TICKET_PAYLOAD)
    assert resp.status_code == 401


# ── Client lists their tickets ───────────────────────────────────


@pytest.mark.asyncio
async def test_list_my_tickets(
    client: AsyncClient, client_headers
):
    # create one first
    await client.post(
        "/tickets", json=TICKET_PAYLOAD, headers=client_headers
    )
    resp = await client.get(
        "/tickets/my", headers=client_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_list_my_tickets_filter_by_status(
    client: AsyncClient, client_headers
):
    resp = await client.get(
        "/tickets/my?status=pending",
        headers=client_headers,
    )
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] == "pending"


# ── Get single ticket ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ticket_as_owner(
    client: AsyncClient, client_headers
):
    create = await client.post(
        "/tickets", json=TICKET_PAYLOAD, headers=client_headers
    )
    ticket_id = create.json()["id"]

    resp = await client.get(
        f"/tickets/{ticket_id}", headers=client_headers
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == ticket_id


# ── Admin transitions ticket ────────────────────────────────────


@pytest.mark.asyncio
async def test_transition_ticket(
    client: AsyncClient,
    client_headers,
    admin_headers,
):
    create = await client.post(
        "/tickets", json=TICKET_PAYLOAD, headers=client_headers
    )
    ticket_id = create.json()["id"]

    resp = await client.put(
        f"/tickets/{ticket_id}/status",
        json={
            "to_status": "under_review",
            "comment": "Looking into this now",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "under_review"


@pytest.mark.asyncio
async def test_invalid_transition_rejected(
    client: AsyncClient,
    client_headers,
    admin_headers,
):
    create = await client.post(
        "/tickets", json=TICKET_PAYLOAD, headers=client_headers
    )
    ticket_id = create.json()["id"]

    # pending → resolved is not allowed
    resp = await client.put(
        f"/tickets/{ticket_id}/status",
        json={
            "to_status": "resolved",
            "comment": "Skipping steps",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422


# ── Feedback ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_feedback_only_on_resolved(
    client: AsyncClient, client_headers
):
    create = await client.post(
        "/tickets", json=TICKET_PAYLOAD, headers=client_headers
    )
    ticket_id = create.json()["id"]

    # ticket is pending — feedback should fail
    resp = await client.post(
        f"/tickets/{ticket_id}/feedback",
        json={"rating": 5, "comment": "Great!"},
        headers=client_headers,
    )
    assert resp.status_code == 422

