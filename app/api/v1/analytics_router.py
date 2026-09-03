
"""Analytics router — dashboard data for SuperAdmin + permitted managers."""

from fastapi import APIRouter, Depends, Query

from app.core.deps import AsyncDB, require_permission
from app.services import ticket_service

router = APIRouter()


@router.get(
    "/dashboard",
    dependencies=[Depends(require_permission("analytics", "read"))],
)
async def dashboard_summary(db: AsyncDB):
    """
    Single call — assembles the full admin dashboard payload.
    overview + trends + categories + resolution + feedback + agents.
    """
    return await ticket_service.get_dashboard_summary(db)


@router.get(
    "/overview",
    dependencies=[Depends(require_permission("analytics", "read"))],
)
async def overview_stats(db: AsyncDB):
    """Top-level cards: totals, open/resolved, avg hours, avg rating."""
    return await ticket_service.get_overview_stats(db)


@router.get(
    "/tickets",
    dependencies=[Depends(require_permission("analytics", "read"))],
)
async def ticket_trends(
    db: AsyncDB,
    days: int = Query(30, ge=7, le=365),
):
    """Daily created vs resolved for the last N days."""
    return await ticket_service.get_ticket_trends(db, days=days)


@router.get(
    "/categories",
    dependencies=[Depends(require_permission("analytics", "read"))],
)
async def category_breakdown(db: AsyncDB):
    """Ticket count per category — pie/bar chart data."""
    return await ticket_service.get_category_breakdown(db)


@router.get(
    "/resolution",
    dependencies=[Depends(require_permission("analytics", "read"))],
)
async def resolution_metrics(db: AsyncDB):
    """SLA metrics: avg/median/p95 hours + time buckets."""
    return await ticket_service.get_resolution_metrics(db)


@router.get(
    "/agents",
    dependencies=[Depends(require_permission("analytics", "read"))],
)
async def agent_performance(db: AsyncDB):
    """Per-manager: assigned, resolved, rate, avg hours, avg rating."""
    return await ticket_service.get_agent_performance(db)


@router.get(
    "/feedback",
    dependencies=[Depends(require_permission("analytics", "read"))],
)
async def feedback_analytics(db: AsyncDB):
    """Rating distribution (1-5) + 6-month monthly trend."""
    return await ticket_service.get_feedback_analytics(db)

