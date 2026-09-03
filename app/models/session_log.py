"""
Session log.

One row per login and per refresh. This is what answers "when did this
person first log in" and "when does this session expire" without
trusting client-side state -- the JWT is the credential, this table is
the audit trail.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.Base import TimestampMixin, UUIDPkMixin


class SessionLog(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "session_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    auth_method: Mapped[str] = mapped_column(String(20), nullable=False)
    login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
