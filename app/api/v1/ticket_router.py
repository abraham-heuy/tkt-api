"""Ticket router — client and admin endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query

from app.core.deps import (
    AsyncDB,
    ClientUser,
    CurrentUser,
    StaffUser,
    require_permission,
    require_ticket_owner_or_staff,
)
from app.schemas.ticket import (
    FeedbackCreateRequest,
    FeedbackOut,
    TicketAssignRequest,
    TicketCreateRequest,
    TicketOut,
    TicketTransitionOut,
    TicketTransitionRequest,
)
from app.schemas.pagination import PaginatedResponse
from app.services import ticket_service

router = APIRouter()


# ── Client endpoints ─────────────────────────────────────────────

@router.post("", response_model=TicketOut, status_code=201)
async def create_ticket(
    body: TicketCreateRequest,
    current_user: ClientUser,
    db: AsyncDB,
):
    """Client submits a new support ticket."""
    user, _ = current_user  # unpack (User, role_name)
    ticket = await ticket_service.create_ticket(
        db,
        client_id=user.id,
        subject=body.subject,
        description=body.description,
        category=body.category,
    )
    return ticket


@router.get("/my", response_model=PaginatedResponse[TicketOut])
async def list_my_tickets(
    current_user: ClientUser,
    db: AsyncDB,
    status: str | None = Query(None),
    limit: int = Query(25, le=100),
    offset: int = Query(0, ge=0),
):
    """Client views their own tickets."""
    user, _ = current_user  # unpack (User, role_name)
    tickets, total = await ticket_service.list_my_tickets(
        db,
        user.id,
        status_filter=status,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(
        items=tickets, total=total, limit=limit, offset=offset
    )


# ── Shared (owner or staff) ─────────────────────────────────────

@router.get(
    "/{ticket_id}",
    response_model=TicketOut,
    dependencies=[Depends(require_ticket_owner_or_staff())],
)
async def get_ticket(ticket_id: uuid.UUID, db: AsyncDB):
    """Get a single ticket — client sees own, staff sees any."""
    return await ticket_service.get_ticket(db, ticket_id)


@router.get(
    "/{ticket_id}/transitions",
    response_model=list[TicketTransitionOut],
    dependencies=[Depends(require_ticket_owner_or_staff())],
)
async def get_transitions(ticket_id: uuid.UUID, db: AsyncDB):
    """Full audit trail for a ticket."""
    return await ticket_service.list_transitions(db, ticket_id)


# ── Staff endpoints ──────────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedResponse[TicketOut],
    dependencies=[Depends(require_permission("tickets", "read"))],
)
async def list_tickets(
    db: AsyncDB,
    status: str | None = Query(None),
    category: str | None = Query(None),
    assigned_to: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(25, le=100),
    offset: int = Query(0, ge=0),
):
    """Admin/manager ticket queue with filters."""
    tickets, total = await ticket_service.list_tickets(
        db,
        status_filter=status,
        category=category,
        assigned_to=assigned_to,
        search=search,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(
        items=tickets, total=total, limit=limit, offset=offset
    )


@router.put(
    "/{ticket_id}/status",
    response_model=TicketOut,
    dependencies=[Depends(require_permission("tickets", "write"))],
)
async def transition_ticket(
    ticket_id: uuid.UUID,
    body: TicketTransitionRequest,
    current_user: StaffUser,
    db: AsyncDB,
):
    """Move ticket to a new status with a comment."""
    user, _ = current_user  # unpack (User, role_name)
    ticket, _ = await ticket_service.transition_ticket(
        db,
        ticket_id=ticket_id,
        to_status=body.to_status,
        comment=body.comment,
        transitioned_by=user.id,
    )
    return ticket


@router.put(
    "/{ticket_id}/assign",
    response_model=TicketOut,
    dependencies=[Depends(require_permission("tickets", "assign"))],
)
async def assign_ticket(
    ticket_id: uuid.UUID,
    body: TicketAssignRequest,
    current_user: StaffUser,
    db: AsyncDB,
):
    """Assign or reassign a ticket to a manager."""
    user, _ = current_user  # unpack (User, role_name)
    return await ticket_service.assign_ticket(
        db,
        ticket_id=ticket_id,
        assigned_to=body.assigned_to,
        assigned_by=user.id,
    )


# ── Feedback (client, post-resolve) ─────────────────────────────

@router.post(
    "/{ticket_id}/feedback",
    response_model=FeedbackOut,
    status_code=201,
)
async def submit_feedback(
    ticket_id: uuid.UUID,
    body: FeedbackCreateRequest,
    current_user: ClientUser,
    db: AsyncDB,
):
    """Client submits feedback after ticket is resolved."""
    user, _ = current_user  # unpack (User, role_name)
    return await ticket_service.submit_feedback(
        db,
        ticket_id=ticket_id,
        client_id=user.id,
        rating=body.rating,
        comment=body.comment,
    )


@router.get(
    "/{ticket_id}/feedback",
    response_model=FeedbackOut | None,
    dependencies=[Depends(require_ticket_owner_or_staff())],
)
async def get_feedback(ticket_id: uuid.UUID, db: AsyncDB):
    """Get feedback for a ticket (if any)."""
    return await ticket_service.get_feedback(db, ticket_id)