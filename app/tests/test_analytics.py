
"""Analytics endpoint tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dashboard_summary(
    client: AsyncClient, admin_headers
):
    resp = await client.get(
        "/analytics/dashboard", headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "overview" in data
    assert "ticket_trends" in data
    assert "category_breakdown" in data
    assert "resolution_metrics" in data
    assert "feedback_analytics" in data
    assert "agent_performance" in data


@pytest.mark.asyncio
async def test_overview_stats(
    client: AsyncClient, admin_headers
):
    resp = await client.get(
        "/analytics/overview", headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_tickets" in data
    assert "resolution_rate" in data


@pytest.mark.asyncio
async def test_ticket_trends(
    client: AsyncClient, admin_headers
):
    resp = await client.get(
        "/analytics/tickets?days=7",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_analytics_denied_for_client(
    client: AsyncClient, client_headers
):
    resp = await client.get(
        "/analytics/dashboard", headers=client_headers
    )
    assert resp.status_code == 403

