"""
Tickets -- the core record. status is denormalized here (in addition to
being derivable from ticket_transitions) so listing/filtering tickets
by status never needs a join.
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.Base import TimestampMixin, UUIDPkMixin


class TicketStatus:
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class Ticket(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "tickets"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(4000), nullable=False)
    category: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=TicketStatus.PENDING, index=True, nullable=False
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=True
    )
