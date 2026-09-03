"""User router - admin user management, KYC, manager creation."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import (
    AdminUser,
    AsyncDB,
    StaffUser,
    require_permission,
)
from app.models.Role import Role
from app.models.User import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.user import (
    ManagerCreateRequest,
    UserOut,
    UserUpdateRequest,
    UserWithProfileOut,
)
from app.services import user_service

router = APIRouter()


class ManagerCreateResponse(BaseModel):
    user: UserOut
    recovery_code: str


def _user_out(user, role_name: str) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=role_name,
        auth_method=user.auth_method,
        is_active=user.is_active,
    )


@router.get(
    "",
    response_model=PaginatedResponse[UserWithProfileOut],
    dependencies=[Depends(require_permission("user_management", "read"))],
)
async def list_users(
    db: AsyncDB,
    role: str | None = Query(None),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(25, le=100),
    offset: int = Query(0, ge=0),
):
    pairs, total = await user_service.list_users_with_profiles(
        db,
        role_name=role,
        search=search,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )

    if not pairs:
        return PaginatedResponse(items=[], total=total, limit=limit, offset=offset)

    user_ids = [u.id for u, _ in pairs]
    role_result = await db.execute(
        select(User.id, Role.name)
        .join(Role, Role.id == User.role_id)
        .where(User.id.in_(user_ids))
    )
    role_map = {uid: rname for uid, rname in role_result.all()}

    items = [
        UserWithProfileOut(
            user=_user_out(user, role_map.get(user.id, "client")),
            profile=(None if profile is None else _profile_out(profile)),
        )
        for user, profile in pairs
    ]
    return PaginatedResponse(
        items=items, total=total, limit=limit, offset=offset
    )


@router.get(
    "/{user_id}",
    response_model=UserWithProfileOut,
    dependencies=[Depends(require_permission("user_management", "read"))],
)
async def get_user(user_id: uuid.UUID, db: AsyncDB):
    user, profile = await user_service.get_user_with_profile(db, user_id)

    role_result = await db.execute(
        select(Role.name).where(Role.id == user.role_id)
    )
    role_name = role_result.scalar_one()

    return UserWithProfileOut(
        user=_user_out(user, role_name),
        profile=(None if profile is None else _profile_out(profile)),
    )


@router.put(
    "/{user_id}",
    response_model=UserWithProfileOut,
    dependencies=[Depends(require_permission("user_management", "write"))],
)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    db: AsyncDB,
):
    user, profile = await user_service.update_user_profile(
        db,
        user_id,
        is_active=body.is_active,
        full_name=body.full_name,
        phone=body.phone,
        connection_area=body.connection_area,
    )

    role_result = await db.execute(
        select(Role.name).where(Role.id == user.role_id)
    )
    role_name = role_result.scalar_one()

    return UserWithProfileOut(
        user=_user_out(user, role_name),
        profile=(None if profile is None else _profile_out(profile)),
    )


@router.delete(
    "/{user_id}",
    status_code=204,
    dependencies=[Depends(require_permission("user_management", "delete"))],
)
async def deactivate_user(user_id: uuid.UUID, db: AsyncDB):
    await user_service.deactivate_user(db, user_id)


@router.post(
    "/managers",
    response_model=ManagerCreateResponse,
    status_code=201,
)
async def create_manager(
    body: ManagerCreateRequest,
    current_user: AdminUser,
    db: AsyncDB,
):
    admin_user, _ = current_user
    user, recovery_code, granted = await user_service.create_manager(
        db,
        email=body.email,
        action_group_ids=body.action_group_ids,
        created_by=admin_user.id,
    )

    role_result = await db.execute(
        select(Role.name).where(Role.id == user.role_id)
    )
    role_name = role_result.scalar_one()

    return ManagerCreateResponse(
        user=_user_out(user, role_name),
        recovery_code=recovery_code,
    )


def _profile_out(profile):
    from app.schemas.user import ClientProfileOut
    return ClientProfileOut.model_validate(profile)