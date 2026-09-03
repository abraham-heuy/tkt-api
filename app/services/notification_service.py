
"""
Notification service.

Two-way notification system — clients get ticket updates, admins get
new-ticket and feedback alerts. Each notification is persisted in-app
and optionally pushed via Web Push API to subscribed devices.

Design notes:
  - Every public notify_* function creates the DB record AND attempts
    push delivery in one pass.
  - Push failures are swallowed (logged, not raised) so a dead
    subscription never blocks the main request.
  - The unread-count query is optimised for the badge that runs on
    every page load.
"""

import json
import logging
import uuid

from pywebpush import webpush, WebPushException  # pip install pywebpush
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings as settings  # expects VAPID_PRIVATE_KEY, VAPID_CLAIMS
from app.models.notification import Notification, NotificationType
from app.models.push_subscription import PushSubscription
from app.models.ticket import Ticket
from app.models.ticket_transition import TicketTransition
from app.models.feedback import Feedback
from app.models.User import User
from app.models.Role import Role, RoleName

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  PUBLIC — trigger-based creators (called from ticket_service)
# ══════════════════════════════════════════════════════════════════


async def notify_new_ticket(db: AsyncSession, ticket: Ticket) -> None:
    """Notify all superadmins + managers with ticket-read access."""
    admin_ids = await _get_admin_user_ids(db)

    for uid in admin_ids:
        notif = await _create(
            db,
            user_id=uid,
            ticket_id=ticket.id,
            title="New Ticket Submitted",
            message=f"[{ticket.category}] {ticket.subject}",
            type=NotificationType.NEW_TICKET,
        )
        await _try_push(db, notif)


async def notify_ticket_status_change(
    db: AsyncSession, ticket: Ticket, transition: TicketTransition
) -> None:
    """Notify the ticket owner (client) about a status change."""
    notif = await _create(
        db,
        user_id=ticket.client_id,
        ticket_id=ticket.id,
        title="Ticket Updated",
        message=(
            f"Your ticket '{ticket.subject}' moved to "
            f"{transition.to_status.replace('_', ' ').title()}. "
            f"Note: {transition.comment}"
        ),
        type=NotificationType.STATUS_CHANGE,
    )
    await _try_push(db, notif)


async def notify_ticket_assigned(
    db: AsyncSession, ticket: Ticket, assignee: User
) -> None:
    """Notify the manager they've been assigned a ticket."""
    notif = await _create(
        db,
        user_id=assignee.id,
        ticket_id=ticket.id,
        title="Ticket Assigned to You",
        message=f"[{ticket.category}] {ticket.subject}",
        type=NotificationType.ASSIGNMENT,
    )
    await _try_push(db, notif)


async def notify_feedback_received(
    db: AsyncSession, ticket: Ticket, feedback: Feedback
) -> None:
    """Notify the assigned manager (or all admins) about new feedback."""
    targets = (
        [ticket.assigned_to] if ticket.assigned_to
        else await _get_admin_user_ids(db)
    )

    for uid in targets:
        notif = await _create(
            db,
            user_id=uid,
            ticket_id=ticket.id,
            title="Feedback Received",
            message=(
                f"Rating: {'⭐' * feedback.rating} ({feedback.rating}/5) "
                f"on '{ticket.subject}'"
            ),
            type=NotificationType.FEEDBACK,
        )
        await _try_push(db, notif)


# ══════════════════════════════════════════════════════════════════
#  PUBLIC — read / manage (called from notification router)
# ══════════════════════════════════════════════════════════════════


async def list_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    unread_only: bool = False,
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[Notification], int]:
    """Paginated notification list for a user."""
    base = select(Notification).where(Notification.user_id == user_id)

    if unread_only:
        base = base.where(Notification.is_read == False)  # noqa: E712

    total = await _count(db, base)
    stmt = base.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Badge count — optimised single-column indexed query."""
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
    )
    return result.scalar_one()


async def mark_read(db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification:
    """Mark a single notification as read."""
    notif = await db.get(Notification, notification_id)
    if notif is None or notif.user_id != user_id:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, "notification not found")

    notif.is_read = True
    await db.commit()
    await db.refresh(notif)
    return notif


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Mark all unread notifications as read. Returns count affected."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount


# ══════════════════════════════════════════════════════════════════
#  PUSH SUBSCRIPTION MANAGEMENT
# ══════════════════════════════════════════════════════════════════


async def subscribe_push(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
) -> PushSubscription:
    """Register or upsert a push subscription for a device."""
    # upsert — endpoint is unique, same browser re-subscribing
    existing = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    )
    sub = existing.scalar_one_or_none()

    if sub is not None:
        sub.user_id = user_id
        sub.p256dh_key = p256dh_key
        sub.auth_key = auth_key
    else:
        sub = PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key=p256dh_key,
            auth_key=auth_key,
        )
        db.add(sub)

    await db.commit()
    await db.refresh(sub)
    return sub


async def unsubscribe_push(db: AsyncSession, user_id: uuid.UUID, endpoint: str) -> None:
    """Remove a push subscription."""
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is not None:
        await db.delete(sub)
        await db.commit()


# ══════════════════════════════════════════════════════════════════
#  PRIVATE — helpers
# ══════════════════════════════════════════════════════════════════


async def _create(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    ticket_id: uuid.UUID | None,
    title: str,
    message: str,
    type: str,
) -> Notification:
    """Persist a notification record."""
    notif = Notification(
        user_id=user_id,
        ticket_id=ticket_id,
        title=title,
        message=message,
        type=type,
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    return notif


async def _try_push(db: AsyncSession, notif: Notification) -> None:
    """
    Attempt Web Push delivery to all subscribed devices for the user.
    Failures are logged, never raised — push is best-effort.
    Stale subscriptions (410 Gone) are auto-cleaned.
    """
    result = await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == notif.user_id)
    )
    subscriptions = result.scalars().all()

    if not subscriptions:
        return

    payload = json.dumps({
        "title": notif.title,
        "body": notif.message,
        "type": notif.type,
        "ticket_id": str(notif.ticket_id) if notif.ticket_id else None,
        "notification_id": str(notif.id),
    })

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh_key,
                        "auth": sub.auth_key,
                    },
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims=settings.VAPID_CLAIMS,
            )
            # mark push as sent
            notif.push_sent = True
            await db.commit()

        except WebPushException as e:
            logger.warning("push failed for %s: %s", sub.endpoint, e)
            # 410 Gone = browser unsubscribed, clean up
            if hasattr(e, "response") and e.response is not None:
                if e.response.status_code == 410:
                    await db.delete(sub)
                    await db.commit()
                    logger.info("removed stale subscription: %s", sub.endpoint)

        except Exception as e:
            logger.error("unexpected push error for %s: %s", sub.endpoint, e)


async def _get_admin_user_ids(db: AsyncSession) -> list[uuid.UUID]:
    """Get all active superadmin + manager user IDs for broadcast notifications."""
    stmt = (
        select(User.id)
        .join(Role, Role.id == User.role_id)
        .where(
            Role.name.in_([RoleName.SUPER_ADMIN, RoleName.MANAGER]),
            User.is_active == True,  # noqa: E712
        )
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def _count(db: AsyncSession, base_stmt) -> int:
    """Total count from a base select."""
    count_result = await db.execute(
        select(func.count()).select_from(base_stmt.subquery())
    )
    return count_result.scalar_one()

