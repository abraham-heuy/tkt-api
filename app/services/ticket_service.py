
"""
Ticket service.

Covers the full ticket lifecycle for both client and manager consoles,
plus dashboard analytics with trend data for the admin panel.

Design notes:
  - Ticket status is denormalized on the ticket row for fast filtering.
  - Every status change appends to ticket_transitions (audit trail).
  - Notification dispatch is called but not awaited in-line — the
    notification service handles its own persistence and push delivery.
  - Analytics queries use raw SQL aggregations for performance; they
    never load full ORM objects.
"""

import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import case, func, select, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket, TicketStatus
from app.models.ticket_transition import TicketTransition
from app.models.feedback import Feedback
from app.models.User import User
from app.services import notification_service


# ── Status flow validation ───────────────────────────────────────

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    TicketStatus.PENDING:      [TicketStatus.UNDER_REVIEW],
    TicketStatus.UNDER_REVIEW: [TicketStatus.IN_PROGRESS, TicketStatus.PENDING],
    TicketStatus.IN_PROGRESS:  [TicketStatus.RESOLVED, TicketStatus.UNDER_REVIEW],
    TicketStatus.RESOLVED:     [],  # terminal state
}


def _validate_transition(current: str, target: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"cannot move from '{current}' to '{target}' — "
            f"allowed: {allowed or 'none (terminal state)'}",
        )


# ══════════════════════════════════════════════════════════════════
#  CLIENT-FACING
# ══════════════════════════════════════════════════════════════════


async def create_ticket(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    subject: str,
    description: str,
    category: str,
) -> Ticket:
    """Client submits a new ticket — starts as PENDING."""
    ticket = Ticket(
        client_id=client_id,
        subject=subject,
        description=description,
        category=category,
        status=TicketStatus.PENDING,
    )
    db.add(ticket)
    await db.flush()

    transition = TicketTransition(
        ticket_id=ticket.id,
        from_status="new",
        to_status=TicketStatus.PENDING,
        comment="Ticket created",
        transitioned_by=client_id,
    )
    db.add(transition)
    await db.commit()
    await db.refresh(ticket)

    await notification_service.notify_new_ticket(db, ticket)
    return ticket


async def list_my_tickets(
    db: AsyncSession,
    client_id: uuid.UUID,
    *,
    status_filter: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Ticket], int]:
    """Client views their own tickets with optional status filter."""
    base = select(Ticket).where(Ticket.client_id == client_id)

    if status_filter is not None:
        base = base.where(Ticket.status == status_filter)

    total = await _count(db, base)
    stmt = base.order_by(Ticket.updated_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def get_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> Ticket:
    """Fetch a single ticket or 404."""
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket not found")
    return ticket


async def get_ticket_with_transitions(
    db: AsyncSession, ticket_id: uuid.UUID
) -> tuple[Ticket, list[TicketTransition]]:
    """Fetch ticket + full state history (audit trail)."""
    ticket = await get_ticket(db, ticket_id)
    transitions = await list_transitions(db, ticket_id)
    return ticket, transitions


async def submit_feedback(
    db: AsyncSession,
    *,
    ticket_id: uuid.UUID,
    client_id: uuid.UUID,
    rating: int,
    comment: str | None = None,
) -> Feedback:
    """Client submits feedback after ticket is resolved."""
    ticket = await get_ticket(db, ticket_id)

    if ticket.client_id != client_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your ticket")
    if ticket.status != TicketStatus.RESOLVED:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "feedback is only allowed on resolved tickets",
        )

    existing = await db.execute(
        select(Feedback).where(Feedback.ticket_id == ticket_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "feedback already submitted")

    feedback = Feedback(
        ticket_id=ticket_id,
        client_id=client_id,
        rating=rating,
        comment=comment,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    await notification_service.notify_feedback_received(db, ticket, feedback)
    return feedback


# ══════════════════════════════════════════════════════════════════
#  MANAGER / ADMIN
# ══════════════════════════════════════════════════════════════════


async def list_tickets(
    db: AsyncSession,
    *,
    status_filter: str | None = None,
    category: str | None = None,
    assigned_to: uuid.UUID | None = None,
    search: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Ticket], int]:
    """Admin/manager ticket queue with filters."""
    base = select(Ticket)

    if status_filter is not None:
        base = base.where(Ticket.status == status_filter)
    if category is not None:
        base = base.where(Ticket.category == category)
    if assigned_to is not None:
        base = base.where(Ticket.assigned_to == assigned_to)
    if search is not None:
        pattern = f"%{search}%"
        base = base.where(
            Ticket.subject.ilike(pattern) | Ticket.description.ilike(pattern)
        )

    total = await _count(db, base)
    stmt = base.order_by(Ticket.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def transition_ticket(
    db: AsyncSession,
    *,
    ticket_id: uuid.UUID,
    to_status: str,
    comment: str,
    transitioned_by: uuid.UUID,
) -> tuple[Ticket, TicketTransition]:
    """
    Move a ticket to a new status.
    Validates the transition, logs it, and fires notifications.
    """
    ticket = await get_ticket(db, ticket_id)
    _validate_transition(ticket.status, to_status)

    from_status = ticket.status
    ticket.status = to_status

    transition = TicketTransition(
        ticket_id=ticket.id,
        from_status=from_status,
        to_status=to_status,
        comment=comment,
        transitioned_by=transitioned_by,
    )
    db.add(transition)
    await db.commit()
    await db.refresh(ticket)
    await db.refresh(transition)

    await notification_service.notify_ticket_status_change(db, ticket, transition)
    return ticket, transition


async def assign_ticket(
    db: AsyncSession,
    *,
    ticket_id: uuid.UUID,
    assigned_to: uuid.UUID,
    assigned_by: uuid.UUID,
) -> Ticket:
    """Assign or reassign a ticket to a manager."""
    ticket = await get_ticket(db, ticket_id)

    assignee = await db.get(User, assigned_to)
    if assignee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "assignee not found")

    ticket.assigned_to = assigned_to
    await db.commit()
    await db.refresh(ticket)

    await notification_service.notify_ticket_assigned(db, ticket, assignee)
    return ticket


async def list_transitions(
    db: AsyncSession, ticket_id: uuid.UUID
) -> list[TicketTransition]:
    """Full audit trail for a ticket, oldest first."""
    stmt = (
        select(TicketTransition)
        .where(TicketTransition.ticket_id == ticket_id)
        .order_by(TicketTransition.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_feedback(
    db: AsyncSession, ticket_id: uuid.UUID
) -> Feedback | None:
    """Get feedback for a specific ticket (if any)."""
    result = await db.execute(
        select(Feedback).where(Feedback.ticket_id == ticket_id)
    )
    return result.scalar_one_or_none()


# ══════════════════════════════════════════════════════════════════
#  ANALYTICS & DASHBOARD
# ══════════════════════════════════════════════════════════════════


async def get_overview_stats(db: AsyncSession) -> dict:
    """
    Top-level dashboard cards:
    total, open, resolved, avg resolution hours, avg rating.
    """
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    status_counts = await db.execute(
        select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
    )
    counts = {status: count for status, count in status_counts.all()}

    total = sum(counts.values())
    resolved = counts.get(TicketStatus.RESOLVED, 0)
    open_tickets = total - resolved

    avg_resolution = await db.execute(
        select(
            func.avg(
                extract("epoch", TicketTransition.created_at - Ticket.created_at) / 3600
            )
        )
        .select_from(TicketTransition)
        .join(Ticket, Ticket.id == TicketTransition.ticket_id)
        .where(TicketTransition.to_status == TicketStatus.RESOLVED)
    )
    avg_hours = avg_resolution.scalar_one_or_none()

    avg_rating_result = await db.execute(select(func.avg(Feedback.rating)))
    avg_rating = avg_rating_result.scalar_one_or_none()

    recent_count = await db.execute(
        select(func.count(Ticket.id)).where(Ticket.created_at >= thirty_days_ago)
    )

    return {
        "total_tickets": total,
        "open_tickets": open_tickets,
        "resolved_tickets": resolved,
        "pending": counts.get(TicketStatus.PENDING, 0),
        "under_review": counts.get(TicketStatus.UNDER_REVIEW, 0),
        "in_progress": counts.get(TicketStatus.IN_PROGRESS, 0),
        "avg_resolution_hours": round(avg_hours, 1) if avg_hours else None,
        "avg_feedback_rating": round(avg_rating, 2) if avg_rating else None,
        "tickets_last_30_days": recent_count.scalar_one(),
        "resolution_rate": round((resolved / total) * 100, 1) if total > 0 else 0,
    }


async def get_ticket_trends(db: AsyncSession, *, days: int = 30) -> list[dict]:
    """
    Daily ticket volume for the last N days.
    Returns [{date, created, resolved}, ...] for charting.
    """
    since = datetime.utcnow() - timedelta(days=days)

    created_stmt = (
        select(
            func.date_trunc("day", Ticket.created_at).label("day"),
            func.count(Ticket.id).label("created"),
        )
        .where(Ticket.created_at >= since)
        .group_by("day")
        .order_by("day")
    )
    created_result = await db.execute(created_stmt)
    created_map = {row.day.date(): row.created for row in created_result.all()}

    resolved_stmt = (
        select(
            func.date_trunc("day", TicketTransition.created_at).label("day"),
            func.count(TicketTransition.id).label("resolved"),
        )
        .where(
            and_(
                TicketTransition.to_status == TicketStatus.RESOLVED,
                TicketTransition.created_at >= since,
            )
        )
        .group_by("day")
        .order_by("day")
    )
    resolved_result = await db.execute(resolved_stmt)
    resolved_map = {row.day.date(): row.resolved for row in resolved_result.all()}

    all_days = sorted(set(list(created_map.keys()) + list(resolved_map.keys())))
    return [
        {
            "date": str(d),
            "created": created_map.get(d, 0),
            "resolved": resolved_map.get(d, 0),
        }
        for d in all_days
    ]


async def get_category_breakdown(db: AsyncSession) -> list[dict]:
    """Ticket count per category — for pie/bar charts."""
    stmt = (
        select(Ticket.category, func.count(Ticket.id).label("count"))
        .group_by(Ticket.category)
        .order_by(func.count(Ticket.id).desc())
    )
    result = await db.execute(stmt)
    return [{"category": row.category, "count": row.count} for row in result.all()]


async def get_agent_performance(db: AsyncSession) -> list[dict]:
    """
    Per-manager metrics:
    tickets assigned, resolved, avg resolution hours, avg rating.
    """
    stmt = (
        select(
            Ticket.assigned_to,
            func.count(Ticket.id).label("assigned"),
            func.count(
                case((Ticket.status == TicketStatus.RESOLVED, Ticket.id))
            ).label("resolved"),
        )
        .where(Ticket.assigned_to.isnot(None))
        .group_by(Ticket.assigned_to)
    )
    result = await db.execute(stmt)
    rows = result.all()

    performance = []
    for row in rows:
        manager_id = row.assigned_to

        avg_res = await db.execute(
            select(
                func.avg(
                    extract("epoch", TicketTransition.created_at - Ticket.created_at)
                    / 3600
                )
            )
            .select_from(TicketTransition)
            .join(Ticket, Ticket.id == TicketTransition.ticket_id)
            .where(
                and_(
                    Ticket.assigned_to == manager_id,
                    TicketTransition.to_status == TicketStatus.RESOLVED,
                )
            )
        )
        avg_hours = avg_res.scalar_one_or_none()

        avg_fb = await db.execute(
            select(func.avg(Feedback.rating))
            .select_from(Feedback)
            .join(Ticket, Ticket.id == Feedback.ticket_id)
            .where(Ticket.assigned_to == manager_id)
        )
        avg_rating = avg_fb.scalar_one_or_none()

        manager = await db.get(User, manager_id)

        performance.append({
            "manager_id": str(manager_id),
            "email": manager.email if manager else "unknown",
            "tickets_assigned": row.assigned,
            "tickets_resolved": row.resolved,
            "resolution_rate": (
                round((row.resolved / row.assigned) * 100, 1)
                if row.assigned > 0 else 0
            ),
            "avg_resolution_hours": round(avg_hours, 1) if avg_hours else None,
            "avg_feedback_rating": round(avg_rating, 2) if avg_rating else None,
        })

    return sorted(performance, key=lambda x: x["tickets_resolved"], reverse=True)


async def get_resolution_metrics(db: AsyncSession) -> dict:
    """SLA-style metrics: avg/median/p95 resolution time, time buckets."""
    stmt = (
        select(
            extract("epoch", TicketTransition.created_at - Ticket.created_at) / 3600
        )
        .select_from(TicketTransition)
        .join(Ticket, Ticket.id == TicketTransition.ticket_id)
        .where(TicketTransition.to_status == TicketStatus.RESOLVED)
    )
    result = await db.execute(stmt)
    hours_list = sorted([row[0] for row in result.all()])

    if not hours_list:
        return {
            "total_resolved": 0,
            "avg_hours": None,
            "median_hours": None,
            "p95_hours": None,
            "buckets": [],
        }

    n = len(hours_list)
    avg_h = sum(hours_list) / n
    median_h = hours_list[n // 2]
    p95_h = hours_list[int(n * 0.95)]

    buckets = {"<1h": 0, "1-4h": 0, "4-12h": 0, "12-24h": 0, "24-48h": 0, ">48h": 0}
    for h in hours_list:
        if h < 1:
            buckets["<1h"] += 1
        elif h < 4:
            buckets["1-4h"] += 1
        elif h < 12:
            buckets["4-12h"] += 1
        elif h < 24:
            buckets["12-24h"] += 1
        elif h < 48:
            buckets["24-48h"] += 1
        else:
            buckets[">48h"] += 1

    return {
        "total_resolved": n,
        "avg_hours": round(avg_h, 1),
        "median_hours": round(median_h, 1),
        "p95_hours": round(p95_h, 1),
        "buckets": [{"range": k, "count": v} for k, v in buckets.items()],
    }


async def get_feedback_analytics(db: AsyncSession) -> dict:
    """Feedback distribution and monthly trends."""
    dist_stmt = (
        select(Feedback.rating, func.count(Feedback.id).label("count"))
        .group_by(Feedback.rating)
        .order_by(Feedback.rating)
    )
    dist_result = await db.execute(dist_stmt)
    distribution = {row.rating: row.count for row in dist_result.all()}

    stats_result = await db.execute(
        select(func.count(Feedback.id), func.avg(Feedback.rating))
    )
    total, avg_rating = stats_result.one()

    six_months_ago = datetime.utcnow() - timedelta(days=180)
    trend_stmt = (
        select(
            func.date_trunc("month", Feedback.created_at).label("month"),
            func.avg(Feedback.rating).label("avg_rating"),
            func.count(Feedback.id).label("count"),
        )
        .where(Feedback.created_at >= six_months_ago)
        .group_by("month")
        .order_by("month")
    )
    trend_result = await db.execute(trend_stmt)
    monthly_trend = [
        {
            "month": str(row.month.date()),
            "avg_rating": round(row.avg_rating, 2),
            "count": row.count,
        }
        for row in trend_result.all()
    ]

    return {
        "total_feedback": total,
        "avg_rating": round(avg_rating, 2) if avg_rating else None,
        "distribution": {str(k): distribution.get(k, 0) for k in range(1, 6)},
        "monthly_trend": monthly_trend,
    }


async def get_dashboard_summary(db: AsyncSession) -> dict:
    """
    Single call that assembles the full admin dashboard payload.
    Aggregates all analytics into one response for the frontend.
    """
    overview = await get_overview_stats(db)
    trends = await get_ticket_trends(db, days=30)
    categories = await get_category_breakdown(db)
    resolution = await get_resolution_metrics(db)
    feedback = await get_feedback_analytics(db)
    agents = await get_agent_performance(db)

    return {
        "overview": overview,
        "ticket_trends": trends,
        "category_breakdown": categories,
        "resolution_metrics": resolution,
        "feedback_analytics": feedback,
        "agent_performance": agents,
    }


# ── Private helpers ──────────────────────────────────────────────


async def _count(db: AsyncSession, base_stmt) -> int:
    """Get total count from a base select statement."""
    count_result = await db.execute(
        select(func.count()).select_from(base_stmt.subquery())
    )
    return count_result.scalar_one()

