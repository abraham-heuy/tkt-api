"""Notification router — in-app + push subscription management."""

import uuid

from fastapi import APIRouter, Query

from app.core.deps import AsyncDB, CurrentUser
from app.schemas.notification import NotificationOut, PushSubscribeRequest
from app.schemas.pagination import PaginatedResponse
from app.services import notification_service

router = APIRouter()


@router.get("", response_model=PaginatedResponse[NotificationOut])
async def list_notifications(
    current: CurrentUser,
    db: AsyncDB,
    unread_only: bool = Query(False),
    limit: int = Query(30, le=100),
    offset: int = Query(0, ge=0),
):
    """Get paginated notifications for the current user."""
    user, _ = current  # unpack tuple
    items, total = await notification_service.list_notifications(
        db,
        user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(
        items=items, total=total, limit=limit, offset=offset
    )


@router.get("/unread-count")
async def unread_count(current: CurrentUser, db: AsyncDB):
    """Badge count for the notification bell."""
    user, _ = current
    count = await notification_service.unread_count(db, user.id)
    return {"unread_count": count}


@router.put("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: uuid.UUID,
    current: CurrentUser,
    db: AsyncDB,
):
    """Mark a single notification as read."""
    user, _ = current
    return await notification_service.mark_read(
        db, notification_id, user.id
    )


@router.put("/read-all")
async def mark_all_read(current: CurrentUser, db: AsyncDB):
    """Mark all unread notifications as read."""
    user, _ = current
    count = await notification_service.mark_all_read(
        db, user.id
    )
    return {"marked_read": count}


@router.post("/push/subscribe", status_code=201)
async def subscribe_push(
    body: PushSubscribeRequest,
    current: CurrentUser,
    db: AsyncDB,
):
    """Register a Web Push subscription for this device."""
    user, _ = current
    sub = await notification_service.subscribe_push(
        db,
        user.id,
        endpoint=body.endpoint,
        p256dh_key=body.p256dh_key,
        auth_key=body.auth_key,
    )
    return {"id": str(sub.id), "endpoint": sub.endpoint}


@router.delete("/push/subscribe", status_code=204)
async def unsubscribe_push(
    body: PushSubscribeRequest,
    current: CurrentUser,
    db: AsyncDB,
):
    """Remove a Web Push subscription."""
    user, _ = current
    await notification_service.unsubscribe_push(
        db, user.id, body.endpoint
    )