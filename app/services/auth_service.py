"""
Auth service.

Two flows live here:
  - authenticate_with_google: verify a Google id_token, get-or-create
    the client user + profile, log the session, issue client cookies.
  - authenticate_admin: check email exists, verify pin, log the
    session, issue admin cookies. Used for both manager and
    super_admin -- the role on the user row decides what they can see.

Every successful login writes a SessionLog row. That is the durable
record of "first login" and "when this session expires" -- the JWT
itself is just the bearer credential.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.utils.security import (
    AuthAudience,
    TokenType,
    create_token,
    generate_recovery_code,
    hash_secret,
    verify_secret,
)
from app.models.client_profile import ClientProfile
from app.models.Role import Role, RoleName
from app.models.session_log import SessionLog
from app.models.User import AuthMethod, User

settings = get_settings()


async def _get_role_id(db: AsyncSession, name: str) -> uuid.UUID:
    result = await db.execute(select(Role.id).where(Role.name == name))
    role_id = result.scalar_one_or_none()
    if role_id is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"role '{name}' is not seeded",
        )
    return role_id


async def _log_session(
    db: AsyncSession,
    user: User,
    auth_method: str,
    refresh_expires_at: datetime,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    db.add(
        SessionLog(
            user_id=user.id,
            auth_method=auth_method,
            login_at=datetime.now(timezone.utc),
            refresh_expires_at=refresh_expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    user.last_login_at = datetime.now(timezone.utc)


async def _role_name(
    db: AsyncSession, role_id: uuid.UUID
) -> str:
    result = await db.execute(
        select(Role.name).where(Role.id == role_id)
    )
    return result.scalar_one()


async def authenticate_with_google(
    db: AsyncSession,
    google_id_token_str: str,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, str, datetime, str, datetime]:
    """Verify Google id_token, return (user, access, exp, refresh, exp)."""
    try:
        claims = google_id_token.verify_oauth2_token(
            google_id_token_str,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid google token"
        ) from exc

    google_sub = claims["sub"]
    email = claims["email"]
    full_name = claims.get("name", email)
    avatar_url = claims.get("picture")

    result = await db.execute(
        select(User).where(User.google_sub == google_sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        client_role_id = await _get_role_id(db, RoleName.CLIENT)
        user = User(
            email=email,
            role_id=client_role_id,
            auth_method=AuthMethod.GOOGLE,
            google_sub=google_sub,
        )
        db.add(user)
        await db.flush()
        db.add(
            ClientProfile(
                user_id=user.id,
                full_name=full_name,
                avatar_url=avatar_url,
            )
        )

    if not user.is_active:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "account is deactivated"
        )

    access, access_exp = create_token(
        str(user.id), RoleName.CLIENT,
        AuthAudience.CLIENT, TokenType.ACCESS,
    )
    refresh, refresh_exp = create_token(
        str(user.id), RoleName.CLIENT,
        AuthAudience.CLIENT, TokenType.REFRESH,
    )
    await _log_session(
        db, user, AuthMethod.GOOGLE,
        refresh_exp, ip_address, user_agent,
    )
    await db.commit()
    return user, access, access_exp, refresh, refresh_exp


async def email_exists(db: AsyncSession, email: str) -> bool:
    result = await db.execute(
        select(User.id).where(User.email == email)
    )
    return result.scalar_one_or_none() is not None


async def authenticate_admin(
    db: AsyncSession,
    email: str,
    pin: str,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, str, str, datetime, str, datetime]:
    """Verify email + pin for manager or super_admin."""
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()

    if (
        user is None
        or user.pin_hash is None
        or not verify_secret(pin, user.pin_hash)
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid email or pin"
        )
    if not user.is_active:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "account is deactivated"
        )

    role_name = await _role_name(db, user.role_id)
    access, access_exp = create_token(
        str(user.id), role_name,
        AuthAudience.ADMIN, TokenType.ACCESS,
    )
    refresh, refresh_exp = create_token(
        str(user.id), role_name,
        AuthAudience.ADMIN, TokenType.REFRESH,
    )
    await _log_session(
        db, user, AuthMethod.CREDENTIALS,
        refresh_exp, ip_address, user_agent,
    )
    await db.commit()
    return user, role_name, access, access_exp, refresh, refresh_exp


async def create_admin_account(
    db: AsyncSession,
    email: str,
    role_name: str,
    created_by: uuid.UUID,
) -> tuple[User, str]:
    """Create a manager/super_admin shell account."""
    role_id = await _get_role_id(db, role_name)
    recovery_code = generate_recovery_code()
    user = User(
        email=email,
        role_id=role_id,
        auth_method=AuthMethod.CREDENTIALS,
        recovery_code_hash=hash_secret(recovery_code),
    )
    db.add(user)
    await db.flush()
    return user, recovery_code


async def reset_pin_with_recovery_code(
    db: AsyncSession,
    email: str,
    recovery_code: str,
    new_pin: str,
) -> None:
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    if (
        user is None
        or user.recovery_code_hash is None
        or not verify_secret(recovery_code, user.recovery_code_hash)
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid email or recovery code",
        )
    user.pin_hash = hash_secret(new_pin)
    await db.commit()