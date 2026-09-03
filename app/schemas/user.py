"""User, client profile, and manager-permission schemas."""

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClientProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str
    phone: str | None = None
    connection_area: str | None = None
    avatar_url: str | None = None
    apartment: str | None = None
    notes: str | None = None

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: str
    auth_method: str
    is_active: bool


class UserWithProfileOut(BaseModel):
    """Returned by GET /users/{id} -- account plus profile, not nested."""

    user: UserOut
    profile: ClientProfileOut | None = None


class ManagerCreateRequest(BaseModel):
    email: EmailStr
    action_group_ids: list[uuid.UUID]


class UserUpdateRequest(BaseModel):
    is_active: bool | None = None
    full_name: str | None = None
    phone: str | None = None
    connection_area: str | None = None
    apartment: str | None = None
    notes: str | None = None

class PermissionGrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_group: str
    action: str


class ClientFeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rating: int
    notes: str | None = None
    improvement: str | None = None
    admin_response: str | None = None
    created_at: datetime
    updated_at: datetime


class ClientFeedbackUpdate(BaseModel):
    rating: int = Field(ge=1, le=5)
    notes: str | None = None
    improvement: str | None = None


class AdminFeedbackResponseUpdate(BaseModel):
    admin_response: str