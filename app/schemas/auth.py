
"""
Auth schemas. Google login and admin/manager login return the same
shape (AuthUserOut) so the frontend does not need two response types.
"""

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class GoogleLoginRequest(BaseModel):
    id_token: str


class CheckEmailRequest(BaseModel):
    email: EmailStr


class CheckEmailResponse(BaseModel):
    exists: bool


class AdminLoginRequest(BaseModel):
    email: EmailStr
    pin: str


class RecoveryResetRequest(BaseModel):
    email: EmailStr
    recovery_code: str
    new_pin: str


class AuthUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: str
    auth_method: str


class RecoveryCodeOut(BaseModel):
    """Shown exactly once, right after account creation."""
    recovery_code: str


class TokenResponse(BaseModel):
    """Returned on successful login — both flows."""
    access_token: str
    user: AuthUserOut

