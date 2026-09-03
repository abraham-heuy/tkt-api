
"""
User service.

Fetching a user always fetches the profile alongside it (for clients)
as two flat queries, never a joined/nested relationship -- see
schemas.user.UserWithProfileOut which returns {user, profile} as
siblings, not profile nested inside user's ORM object.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_profile import ClientProfile
from app.models.Role import Role, RoleName
from app.models.User import User
from app.services import auth_service, permissions_service as permission_service


# ── Single-user fetches ──────────────────────────────────────────


async def get_user_with_profile(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[User, ClientProfile | None]:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    profile = await _fetch_profile(db, user_id)
    return user, profile


async def get_me(
    db: AsyncSession, current_user_id: uuid.UUID
) -> tuple[User, ClientProfile | None]:
    """Shorthand for GET /profile/me — same logic, clearer intent."""
    return await get_user_with_profile(db, current_user_id)


# ── List / search ────────────────────────────────────────────────


async def list_users(
    db: AsyncSession,
    *,
    role_name: str | None = None,
    search: str | None = None,
    is_active: bool | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[User], int]:
    """
    Return a page of users plus total count.

    Filters:
      role_name      – 'client', 'manager', 'superadmin'
      search         – partial match on email or connection_area
      is_active      – true / false
    """
    base = select(User)

    if role_name is not None:
        base = base.join(Role, Role.id == User.role_id).where(Role.name == role_name)

    if is_active is not None:
        base = base.where(User.is_active == is_active)

    if search is not None:
        pattern = f"%{search}%"
        base = base.where(User.email.ilike(pattern))

    # total count (before limit/offset)
    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar_one()

    # page
    stmt = base.order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    users = list(result.scalars().all())

    return users, total


async def list_users_with_profiles(
    db: AsyncSession,
    *,
    role_name: str | None = None,
    search: str | None = None,
    is_active: bool | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[tuple[User, ClientProfile | None]], int]:
    """
    Admin list view — returns each user paired with their profile.
    Two queries: one for users, one batch for profiles.
    """
    users, total = await list_users(
        db,
        role_name=role_name,
        search=search,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )

    if not users:
        return [], total

    # batch-fetch profiles for all user ids in one query
    user_ids = [u.id for u in users]
    profiles_map = await _fetch_profiles_batch(db, user_ids)

    paired = [(u, profiles_map.get(u.id)) for u in users]
    return paired, total


# ── Mutations ────────────────────────────────────────────────────


async def update_user_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    is_active: bool | None = None,
    full_name: str | None = None,
    phone: str | None = None,
    connection_area: str | None = None,
    apartment: str | None = None,
    notes: str | None = None,
) -> tuple[User, ClientProfile | None]:
    user, profile = await get_user_with_profile(db, user_id)

    if is_active is not None:
        user.is_active = is_active

    if profile is not None:
        if full_name is not None:
            profile.full_name = full_name
        if phone is not None:
            profile.phone = phone
        if connection_area is not None:
            profile.connection_area = connection_area
        if apartment is not None:
            profile.apartment = apartment
        if notes is not None:
            profile.notes = notes

    await db.commit()
    await db.refresh(user)
    if profile is not None:
        await db.refresh(profile)
    return user, profile


async def deactivate_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Soft-delete — sets is_active = False. Preserves audit trail."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Hard-delete — permanent removal. Use deactivate_user for soft-delete."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    await db.delete(user)
    await db.commit()


async def create_manager(
    db: AsyncSession,
    email: str,
    action_group_ids: list[uuid.UUID],
    created_by: uuid.UUID,
) -> tuple[User, str, list]:
    """
    Create a manager account and grant its initial permission set.

    Returns (user, recovery_code, granted_permissions).
    """
    user, recovery_code = await auth_service.create_admin_account(
        db, email, RoleName.MANAGER, created_by
    )

    granted = []
    if action_group_ids:
        granted = await permission_service.grant_permissions(
            db, user.id, action_group_ids, created_by
        ) or []

    await db.commit()
    return user, recovery_code, granted


# Private helpers 


async def _fetch_profile(
    db: AsyncSession, user_id: uuid.UUID
) -> ClientProfile | None:
    """Single profile fetch by user_id PK."""
    return await db.get(ClientProfile, user_id)


async def _fetch_profiles_batch(
    db: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ClientProfile]:
    """Batch-fetch profiles for a list of user ids — avoids N+1."""
    if not user_ids:
        return {}
    stmt = select(ClientProfile).where(ClientProfile.user_id.in_(user_ids))
    result = await db.execute(stmt)
    profiles = result.scalars().all()
    return {p.user_id: p for p in profiles}

