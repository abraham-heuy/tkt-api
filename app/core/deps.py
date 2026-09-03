
"""
FastAPI dependencies — auth, permission gates, and DB session.

Design note: User model has NO relationship() to Role (project rule).
So we resolve role_name via an explicit query and pass it alongside
the user as a tuple[User, str] through the dependency chain.
"""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.Role import Role, RoleName
from app.models.User import User
from app.utils.security import AuthAudience, decode_token


# ── DB session ───────────────────────────────────────────────────

AsyncDB = Annotated[AsyncSession, Depends(get_db)]


# ── Internal helpers ─────────────────────────────────────────────

async def _resolve_role(
    db: AsyncSession, role_id: uuid.UUID
) -> str:
    result = await db.execute(
        select(Role.name).where(Role.id == role_id)
    )
    name = result.scalar_one_or_none()
    if name is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "role not found",
        )
    return name


def _extract_token(request: Request) -> str:
    raw = request.headers.get("Authorization", "")
    token = raw.removeprefix("Bearer ").strip()
    if not token:
        token = request.cookies.get("access_token", "")
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "missing token"
        )
    return token

def _decode_any_audience(token: str) -> dict:
    """Try admin audience first, then client."""
    for aud in (AuthAudience.ADMIN, AuthAudience.CLIENT):
        try:
            return decode_token(token, aud)
        except Exception:
            continue
    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "invalid or expired token",
    )


# ── Current user ─────────────────────────────────────────────────

async def get_current_user(
    request: Request, db: AsyncDB
) -> tuple[User, str]:
    """
    Returns (user, role_name). No relationship() needed —
    role is resolved via explicit query.
    """
    token = _extract_token(request)
    payload = _decode_any_audience(token)

    raw_id = payload.get("sub")
    if raw_id is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "malformed token"
        )

    user = await db.get(User, uuid.UUID(str(raw_id)))
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "user not found"
        )
    if not user.is_active:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "account deactivated"
        )

    role_name = await _resolve_role(db, user.role_id)
    return user, role_name


CurrentUser = Annotated[
    tuple[User, str], Depends(get_current_user)
]


# ── Role gates ───────────────────────────────────────────────────

async def require_admin(
    current: CurrentUser,
) -> tuple[User, str]:
    user, role_name = current
    if role_name != RoleName.SUPER_ADMIN:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "superadmin access required",
        )
    return user, role_name


async def require_staff(
    current: CurrentUser,
) -> tuple[User, str]:
    user, role_name = current
    if role_name not in (
        RoleName.SUPER_ADMIN, RoleName.MANAGER
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "staff access required",
        )
    return user, role_name


async def require_client(
    current: CurrentUser,
) -> tuple[User, str]:
    user, role_name = current
    if role_name != RoleName.CLIENT:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "client access required",
        )
    return user, role_name


AdminUser = Annotated[
    tuple[User, str], Depends(require_admin)
]
StaffUser = Annotated[
    tuple[User, str], Depends(require_staff)
]
ClientUser = Annotated[
    tuple[User, str], Depends(require_client)
]


# ── IAM permission gate ─────────────────────────────────────────

def require_permission(service: str, action: str):
    """
    Closure dependency for IAM checks.
    SuperAdmin auto-passes. Client always blocked.
    Manager checked against manager_permissions table.
    """

    async def _check(
        current: CurrentUser, db: AsyncDB
    ) -> None:
        from app.services import permissions_service

        user, role_name = current

        if role_name == RoleName.CLIENT:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "access denied"
            )

        # superadmin bypasses IAM
        if role_name == RoleName.SUPER_ADMIN:
            return

        allowed = await permissions_service.has_permission(
            db,
            user_id=user.id,
            role_name=role_name,
            service_name=service,
            action=action,
        )
        if not allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"no access to {service}:{action}",
            )

    return _check


# ── Ownership check ─────────────────────────────────────────────

def require_ticket_owner_or_staff():
    """Client sees own ticket, staff sees any."""

    async def _check(
        ticket_id: uuid.UUID,
        current: CurrentUser,
        db: AsyncDB,
    ) -> None:
        from app.models.ticket import Ticket

        user, role_name = current

        ticket = await db.get(Ticket, ticket_id)
        if ticket is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "ticket not found",
            )

        if role_name in (
            RoleName.SUPER_ADMIN, RoleName.MANAGER
        ):
            return
        if ticket.client_id != user.id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "not your ticket",
            )

    return _check

