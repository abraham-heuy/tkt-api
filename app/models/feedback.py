"""
Feedback -- one rating per resolved ticket. ticket_id is unique so the
service layer can rely on the database, not application logic, to
enforce "one feedback per ticket".
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.Base import TimestampMixin, UUIDPkMixin


class Feedback(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "feedback"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id"), unique=True, nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
