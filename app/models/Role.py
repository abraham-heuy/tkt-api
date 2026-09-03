"""
Role lookup table.

Kept as a real table (not a bare Python enum) so new roles can be added
without a migration touching every row, and so other tables can carry
a real, indexed foreign key instead of a loose string. Seeded once via
an Alembic data migration with exactly three rows: client, manager,
super_admin.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.Base import UUIDPkMixin


class RoleName:
    CLIENT = "client"
    MANAGER = "manager"
    SUPER_ADMIN = "super_admin"


class Role(UUIDPkMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)