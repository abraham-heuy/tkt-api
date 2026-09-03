"""
Manager permissions -- the actual grant linking a manager user to one
action_group. A super_admin creates these when onboarding a manager;
checking access is a single indexed lookup (user_id, action_group_id).
"""

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.Base import TimestampMixin, UUIDPkMixin


class ManagerPermission(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "manager_permissions"
    __table_args__ = (
        UniqueConstraint("user_id", "action_group_id", name="uq_user_action_group"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    action_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("action_groups.id"), index=True, nullable=False
    )
    granted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
