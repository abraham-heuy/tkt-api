"""
Web Push subscriptions -- one row per browser/device a user has
enabled push on. endpoint is unique because the browser issues one
per registration and re-subscribing should upsert, not duplicate.
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.Base import TimestampMixin, UUIDPkMixin


class PushSubscription(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    p256dh_key: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_key: Mapped[str] = mapped_column(String(255), nullable=False)
