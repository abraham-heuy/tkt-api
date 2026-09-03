"""
Ticket transitions -- append-only state history. Every status change
requires a comment, which doubles as the audit trail and the source
text for the notification sent to the other party.
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.Base import TimestampMixin, UUIDPkMixin


class TicketTransition(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "ticket_transitions"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id"), index=True, nullable=False
    )
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str] = mapped_column(String(2000), nullable=False)
    transitioned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
