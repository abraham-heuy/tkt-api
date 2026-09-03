"""
Notifications -- two-way, in-app on both consoles plus web push.
is_read is indexed because the unread-count badge query runs on almost
every page load for every logged-in user.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.Base import TimestampMixin, UUIDPkMixin


class NotificationType:
    NEW_TICKET = "new_ticket"
    STATUS_CHANGE = "status_change"
    ASSIGNMENT = "assignment"
    FEEDBACK = "feedback"


class Notification(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    push_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
