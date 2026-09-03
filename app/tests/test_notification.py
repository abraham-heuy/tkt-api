
"""Notification endpoint tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType


@pytest.mark.asyncio
async def test_list_notifications_empty(
    client: AsyncClient, client_headers
):
    resp = await client.get(
        "/notifications", headers=client_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_unread_count(
    client: AsyncClient,
    client_headers,
    client_user,
    db: AsyncSession,
):
    # seed a notification directly
    db.add(Notification(
        user_id=client_user.id,
        title="Test",
        message="Test notification",
        type=NotificationType.NEW_TICKET,
    ))
    await db.commit()

    resp = await client.get(
        "/notifications/unread-count",
        headers=client_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["unread_count"] >= 1


@pytest.mark.asyncio
async def test_mark_read(
    client: AsyncClient,
    client_headers,
    client_user,
    db: AsyncSession,
):
    notif = Notification(
        user_id=client_user.id,
        title="Test",
        message="Mark me read",
        type=NotificationType.STATUS_CHANGE,
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)

    resp = await client.put(
        f"/notifications/{notif.id}/read",
        headers=client_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True


@pytest.mark.asyncio
async def test_mark_all_read(
    client: AsyncClient,
    client_headers,
    client_user,
    db: AsyncSession,
):
    for i in range(3):
        db.add(Notification(
            user_id=client_user.id,
            title=f"Notif {i}",
            message=f"Message {i}",
            type=NotificationType.NEW_TICKET,
        ))
    await db.commit()

    resp = await client.put(
        "/notifications/read-all",
        headers=client_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["marked_read"] >= 3

