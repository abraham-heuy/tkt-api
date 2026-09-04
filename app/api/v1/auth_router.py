"""Auth router — Google OAuth for clients, email+PIN for staff."""

import uuid

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.config import get_settings
from app.core.deps import AsyncDB
from app.models.Role import Role
from app.schemas.auth import (
    AdminLoginRequest,
    AuthUserOut,
    CheckEmailRequest,
    CheckEmailResponse,
    GoogleLoginRequest,
    RecoveryResetRequest,
    TokenResponse,
)
from app.services import auth_service
from app.utils.security import AuthAudience, TokenType, create_token, decode_token

router = APIRouter()
settings = get_settings()


async def _get_role_name(db, role_id):
    result = await db.execute(select(Role.name).where(Role.id == role_id))
    return result.scalar_one()


def _set_cookies(
    response: Response,
    access: str,
    access_exp,
    refresh: str,
    refresh_exp,
) -> None:
    response.set_cookie(
        "access_token",
        access,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        expires=int(access_exp.timestamp()),
    )
    response.set_cookie(
        "refresh_token",
        refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/auth",
        expires=int(refresh_exp.timestamp()),
    )


@router.post("/google/callback", response_model=TokenResponse)
async def google_login(
    body: GoogleLoginRequest,
    request: Request,
    response: Response,
    db: AsyncDB,
):
    """Client login — verify Google id_token, issue cookies."""
    user, access, access_exp, refresh, refresh_exp = (
        await auth_service.authenticate_with_google(
            db,
            body.id_token,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    _set_cookies(response, access, access_exp, refresh, refresh_exp)
    return TokenResponse(
        access_token=access,
        user=AuthUserOut(
            id=user.id,
            email=user.email,
            role="client",
            auth_method=user.auth_method,
        ),
    )


@router.post("/check-email", response_model=CheckEmailResponse)
async def check_email(body: CheckEmailRequest, db: AsyncDB):
    """Step 1 of admin login — check if email exists."""
    exists = await auth_service.email_exists(db, body.email)
    return CheckEmailResponse(exists=exists)


@router.post("/login", response_model=TokenResponse)
async def admin_login(
    body: AdminLoginRequest,
    request: Request,
    response: Response,
    db: AsyncDB,
):
    """Step 2 of admin login — verify email + PIN, issue cookies."""
    user, role_name, access, access_exp, refresh, refresh_exp = (
        await auth_service.authenticate_admin(
            db,
            body.email,
            body.pin,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    _set_cookies(response, access, access_exp, refresh, refresh_exp)
    return TokenResponse(
        access_token=access,
        user=AuthUserOut(
            id=user.id,
            email=user.email,
            role=role_name,
            auth_method=user.auth_method,
        ),
    )


@router.post("/reset-pin", status_code=204)
async def reset_pin(body: RecoveryResetRequest, db: AsyncDB):
    """Reset PIN using the one-time recovery code."""
    await auth_service.reset_pin_with_recovery_code(
        db, body.email, body.recovery_code, body.new_pin
    )


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncDB,
):
    """
    Exchange a valid refresh token cookie for new access + refresh tokens.
    Used by the frontend api client on 401 responses.
    """
    refresh_cookie = request.cookies.get("refresh_token")
    if not refresh_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )

    # Try decoding as either admin or client audience
    payload = None
    for aud in (AuthAudience.ADMIN, AuthAudience.CLIENT):
        try:
            payload = decode_token(refresh_cookie, aud)
            break
        except Exception:
            continue

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token",
        )

    user = await db.get(auth_service.User, uuid.UUID(user_id_str))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Determine role and audience
    role_name = await _get_role_name(db, user.role_id)
    audience = AuthAudience.ADMIN if role_name != "client" else AuthAudience.CLIENT

    # Issue new tokens
    access, access_exp = create_token(
        str(user.id), role_name, audience, TokenType.ACCESS
    )
    refresh_new, refresh_exp = create_token(
        str(user.id), role_name, audience, TokenType.REFRESH
    )

    # Set new cookies
    _set_cookies(response, access, access_exp, refresh_new, refresh_exp)

    return {"access_token": access}