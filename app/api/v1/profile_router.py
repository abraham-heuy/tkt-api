"""Profile router — client self-service profile management."""

from fastapi import APIRouter, HTTPException,status

from app.core.deps import AsyncDB, ClientUser, CurrentUser
from app.schemas.user import (
    ClientProfileOut,
    UserOut,
    UserUpdateRequest,
    UserWithProfileOut,
)
from app.services import user_service

router = APIRouter()


@router.get("/me", response_model=UserWithProfileOut)
async def get_my_profile(current_user: CurrentUser, db: AsyncDB):
    """Client fetches their own account + profile."""
    user, role_name = current_user  # unpack tuple: (User, role_name)
    user_profile, profile = await user_service.get_me(db, user.id)
    return UserWithProfileOut(
        user=UserOut(
            id=user_profile.id,
            email=user_profile.email,
            role=role_name,
            auth_method=user_profile.auth_method,
            is_active=user_profile.is_active,
        ),
        profile=(
            ClientProfileOut.model_validate(profile)
            if profile else None
        ),
    )


@router.put("/me", response_model=UserWithProfileOut)
async def update_my_profile(
    body: UserUpdateRequest,
    current_user: ClientUser,
    db: AsyncDB,
):
    """Client updates their own profile fields."""
    user, role_name = current_user  # unpack tuple
    updated_user, profile = await user_service.update_user_profile(
        db,
        user.id,
        full_name=body.full_name,
        phone=body.phone,
        connection_area=body.connection_area,
    )
    return UserWithProfileOut(
        user=UserOut(
            id=updated_user.id,
            email=updated_user.email,
            role=role_name,
            auth_method=updated_user.auth_method,
            is_active=updated_user.is_active,
        ),
        profile=(
            ClientProfileOut.model_validate(profile)
            if profile else None
        ),
    )

from app.schemas.user import (
    ClientFeedbackOut,
    ClientFeedbackUpdate,
)
from app.services import feedback_service

@router.get("/me/feedback", response_model=ClientFeedbackOut)
async def get_my_feedback(current_user: CurrentUser, db: AsyncDB):
    user, _ = current_user
    feedback = await feedback_service.get_feedback_by_user(db, user.id)
    if feedback is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No feedback yet")
    return feedback


@router.put("/me/feedback", response_model=ClientFeedbackOut)
async def update_my_feedback(
    body: ClientFeedbackUpdate,
    current_user: CurrentUser,
    db: AsyncDB,
):
    user, _ = current_user
    return await feedback_service.upsert_feedback(
        db,
        user.id,
        rating=body.rating,
        notes=body.notes,
        improvement=body.improvement,
    )