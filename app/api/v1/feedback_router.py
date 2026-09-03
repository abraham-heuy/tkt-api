import uuid

from fastapi import APIRouter, Depends, Query

from app.core.deps import AsyncDB, StaffUser, require_permission
from app.schemas.pagination import PaginatedResponse
from app.schemas.user import AdminFeedbackResponseUpdate, ClientFeedbackOut
from app.services import feedback_service

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[ClientFeedbackOut],
    dependencies=[Depends(require_permission("feedback", "read"))],
)
async def list_feedback(
    db: AsyncDB,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """List all feedback entries anonymously (no user identity)."""
    items = await feedback_service.list_all_feedback(db, limit, offset)
    total = len(items)
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.put(
    "/{feedback_id}/response",
    response_model=ClientFeedbackOut,
    dependencies=[Depends(require_permission("feedback", "write"))],
)
async def respond_to_feedback(
    feedback_id: uuid.UUID,
    body: AdminFeedbackResponseUpdate,
    db: AsyncDB,
):
    """Admin adds or updates response to a feedback entry."""
    return await feedback_service.update_admin_response(
        db, feedback_id, body.admin_response
    )