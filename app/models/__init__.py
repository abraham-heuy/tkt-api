"""
ORM models.

Design rule: no SQLAlchemy relationship() attributes anywhere in this
package. Every table only exposes plain foreign key columns. Services
join explicitly with select()/join() when they need related data, and
return flat Pydantic schemas. This keeps serialization predictable,
avoids N+1 lazy-loads, and avoids circular nesting in API responses.

Every model is imported here so Alembic's autogenerate can see them
via Base.metadata.
"""

from app.models.action_group import ActionGroup
from app.models.feedback import Feedback
from app.models.client_profile import ClientProfile
from app.models.manager_permission import ManagerPermission
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription
from app.models.Role import Role
from app.models.service_group import ServiceGroup
from app.models.session_log import SessionLog
from app.models.ticket import Ticket
from app.models.ticket_transition import TicketTransition
from app.models.User import User
from app.models.client_feedback import ClientFeedback

__all__ = [
    "ActionGroup",
    "ClientProfile",
    "Feedback",
    "ManagerPermission",
    "Notification",
    "PushSubscription",
    "Role",
    "ServiceGroup",
    "SessionLog",
    "Ticket",
    "TicketTransition",
    "User",
    "ClientFeedback",
]