"""
Action groups -- granular permissions inside a service group, e.g.
tickets:read, tickets:assign, analytics:read. This is the row that
manager_permissions actually points at, which is what makes the access
matrix AWS-IAM-style rather than a flat role check.
"""

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.Base import UUIDPkMixin


class ActionType:
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ASSIGN = "assign"


class ActionGroup(UUIDPkMixin, Base):
    __tablename__ = "action_groups"
    __table_args__ = (UniqueConstraint("service_group_id", "action", name="uq_service_action"),)

    service_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_groups.id"), index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
