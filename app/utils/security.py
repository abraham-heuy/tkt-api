"""
Security primitives shared by both auth flows (client-google, admin-pin).

Tokens are signed JWTs carried in httponly cookies, never in localStorage.
Access tokens are short lived and re-issued from the refresh token, which
is the one that actually encodes the "stay signed in" window:
    - client (google) refresh -> 7 days
    - manager / super_admin refresh -> 24 hours

Two cookie pairs are used (client_* and admin_*) so a person logged into
both consoles in the same browser does not clash.
"""

import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum

from fastapi import Response
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class AuthAudience(str, Enum):
    """Which cookie/console a token belongs to."""

    CLIENT = "client"
    ADMIN = "admin"


def hash_secret(raw: str) -> str:
    """Hash a PIN, password, or recovery code before storage."""
    return pwd_context.hash(raw)


def verify_secret(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def generate_recovery_code() -> str:
    """One-time recovery code issued at account creation, shown once."""
    return secrets.token_hex(8)


def _expiry_for(audience: AuthAudience, token_type: TokenType) -> timedelta:
    if audience == AuthAudience.CLIENT:
        if token_type == TokenType.ACCESS:
            return timedelta(minutes=settings.client_access_token_expire_minutes)
        return timedelta(days=settings.client_refresh_token_expire_days)
    if token_type == TokenType.ACCESS:
        return timedelta(minutes=settings.admin_access_token_expire_minutes)
    return timedelta(hours=settings.admin_refresh_token_expire_hours)


def create_token(
    user_id: str,
    role: str,
    audience: AuthAudience,
    token_type: TokenType,
) -> tuple[str, datetime]:
    """Build a signed JWT and return it with its absolute expiry."""
    expires_at = datetime.now(timezone.utc) + _expiry_for(audience, token_type)
    payload = {
        "sub": user_id,
        "role": role,
        "aud": audience.value,
        "type": token_type.value,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str, expected_audience: AuthAudience) -> dict:
    """Decode and validate a token, raising JWTError on any problem."""
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        audience=expected_audience.value,
    )
    return payload


def cookie_names(audience: AuthAudience) -> tuple[str, str]:
    """Return (access_cookie_name, refresh_cookie_name) for an audience."""
    prefix = audience.value
    return f"{prefix}_access_token", f"{prefix}_refresh_token"


def set_auth_cookies(
    response: Response,
    audience: AuthAudience,
    access_token: str,
    access_expires_at: datetime,
    refresh_token: str,
    refresh_expires_at: datetime,
) -> None:
    access_name, refresh_name = cookie_names(audience)
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "domain": settings.cookie_domain,
        "path": "/",
    }
    now = datetime.now(timezone.utc)
    response.set_cookie(
        access_name, access_token, max_age=int((access_expires_at - now).total_seconds()), **common
    )
    response.set_cookie(
        refresh_name,
        refresh_token,
        max_age=int((refresh_expires_at - now).total_seconds()),
        **common,
    )


def clear_auth_cookies(response: Response, audience: AuthAudience) -> None:
    access_name, refresh_name = cookie_names(audience)
    response.delete_cookie(access_name, domain=settings.cookie_domain, path="/")
    response.delete_cookie(refresh_name, domain=settings.cookie_domain, path="/")


__all__ = [
    "TokenType",
    "AuthAudience",
    "JWTError",
    "hash_secret",
    "verify_secret",
    "generate_recovery_code",
    "create_token",
    "decode_token",
    "cookie_names",
    "set_auth_cookies",
    "clear_auth_cookies",
]