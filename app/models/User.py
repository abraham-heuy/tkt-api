"""
Users entry table.

One table for all three roles (client / manager / super_admin) because
they share the same identity concerns: email, role, active flag, audit
timestamps. What differs is the auth method and the extra data each
role carries elsewhere (ClientProfile for clients, ManagerPermission
rows for managers).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.Base import TimestampMixin, UUIDPkMixin


class AuthMethod:
    GOOGLE = "google"
    CREDENTIALS = "credentials"


class User(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id"), index=True, nullable=False
    )
    auth_method: Mapped[str] = mapped_column(String(20), nullable=False)

    # Only set for credentials auth (manager / super_admin).
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recovery_code_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Only set for google auth (client).
    google_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)