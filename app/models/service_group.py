"""
Service groups -- the top level of the access matrix (e.g. "tickets",
"analytics", "user_management"). A manager is granted access at the
action_group level, never directly here.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.Base import UUIDPkMixin


class ServiceGroup(UUIDPkMixin, Base):
    __tablename__ = "service_groups"

    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
