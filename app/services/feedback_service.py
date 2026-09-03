import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_feedback import ClientFeedback


async def get_feedback_by_user(
    db: AsyncSession, user_id: uuid.UUID
) -> ClientFeedback | None:
    result = await db.execute(
        select(ClientFeedback).where(ClientFeedback.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert_feedback(
    db: AsyncSession,
    user_id: uuid.UUID,
    rating: int,
    notes: str | None,
    improvement: str | None,
) -> ClientFeedback:
    feedback = await get_feedback_by_user(db, user_id)

    if feedback is None:
        feedback = ClientFeedback(
            user_id=user_id,
            rating=rating,
            notes=notes,
            improvement=improvement,
        )
        db.add(feedback)
    else:
        feedback.rating = rating
        feedback.notes = notes
        feedback.improvement = improvement
        # Clear admin response so admin can respond to the new feedback
        feedback.admin_response = None

    await db.commit()
    await db.refresh(feedback)
    return feedback


async def list_all_feedback(
    db: AsyncSession, limit: int = 50, offset: int = 0
) -> list[ClientFeedback]:
    result = await db.execute(
        select(ClientFeedback)
        .order_by(ClientFeedback.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def update_admin_response(
    db: AsyncSession, feedback_id: uuid.UUID, admin_response: str
) -> ClientFeedback:
    feedback = await db.get(ClientFeedback, feedback_id)
    if feedback is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "feedback not found"
        )
    feedback.admin_response = admin_response
    await db.commit()
    await db.refresh(feedback)
    return feedback