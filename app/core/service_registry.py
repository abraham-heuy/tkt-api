
"""
Service registry — seeds the service_groups and action_groups tables.

Run once on first deploy or as part of migrations. Idempotent — skips
existing rows so it's safe to call on every startup if you prefer.

Usage:
    from app.core.service_registry import seed_services
    await seed_services(db)

The registry defines the full IAM matrix. When a SuperAdmin creates a
manager, the frontend fetches GET /services and GET /services/{id}/actions
to build the permission picker UI.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_group import ServiceGroup
from app.models.action_group import ActionGroup, ActionType


# ══════════════════════════════════════════════════════════════════
#  REGISTRY DEFINITION
# ══════════════════════════════════════════════════════════════════

SERVICES: dict[str, dict] = {
    "tickets": {
        "description": "Ticket queue — view, manage, assign, and resolve support tickets",
        "actions": [
            ActionType.READ,      # view ticket list + details
            ActionType.WRITE,     # update status, add comments
            ActionType.ASSIGN,    # assign/reassign tickets to managers
        ],
    },
    "user_management": {
        "description": "User accounts — view client profiles, manage KYC, deactivate accounts",
        "actions": [
            ActionType.READ,      # view user list + profiles
            ActionType.WRITE,     # update user details
            ActionType.DELETE,    # deactivate / hard-delete users
        ],
    },
    "analytics": {
        "description": "Dashboard analytics — ticket trends, resolution metrics, agent performance",
        "actions": [
            ActionType.READ,      # view all analytics dashboards
        ],
    },
    "notifications": {
        "description": "Notification management — view and manage system notifications",
        "actions": [
            ActionType.READ,      # view notifications
            ActionType.WRITE,     # mark read, manage push subscriptions
        ],
    },
    "feedback": {
        "description": "Customer feedback — view ratings and comments on resolved tickets",
        "actions": [
            ActionType.READ,      # view feedback + analytics
        ],
    },
    "manager_admin": {
        "description": "Manager administration — create managers, assign permissions (SuperAdmin only in practice)",
        "actions": [
            ActionType.READ,      # view manager list + their permissions
            ActionType.WRITE,     # create managers, grant permissions
            ActionType.DELETE,    # revoke permissions, deactivate managers
        ],
    },
}


# ══════════════════════════════════════════════════════════════════
#  SEED FUNCTION
# ══════════════════════════════════════════════════════════════════


async def seed_services(db: AsyncSession) -> dict[str, list[str]]:
    """
    Idempotent seed — creates service_groups and action_groups if they
    don't exist. Returns a summary of what was created/skipped.

    Call from:
      - Alembic data migration
      - app startup event (lifespan)
      - CLI command
    """
    summary: dict[str, list[str]] = {}

    for service_name, config in SERVICES.items():
        # upsert service group
        result = await db.execute(
            select(ServiceGroup).where(ServiceGroup.name == service_name)
        )
        service_group = result.scalar_one_or_none()

        if service_group is None:
            service_group = ServiceGroup(
                name=service_name,
                description=config["description"],
            )
            db.add(service_group)
            await db.flush()  # get the id

        # upsert action groups
        created_actions = []
        for action in config["actions"]:
            existing = await db.execute(
                select(ActionGroup).where(
                    ActionGroup.service_group_id == service_group.id,
                    ActionGroup.action == action,
                )
            )
            if existing.scalar_one_or_none() is None:
                db.add(
                    ActionGroup(
                        service_group_id=service_group.id,
                        action=action,
                    )
                )
                created_actions.append(action)

        summary[service_name] = created_actions

    await db.commit()
    return summary


async def get_full_registry(db: AsyncSession) -> list[dict]:
    """
    Returns the full service → actions tree for the frontend
    permission picker UI.

    Response shape:
    [
        {
            "id": "uuid",
            "name": "tickets",
            "description": "...",
            "actions": [
                {"id": "uuid", "action": "read"},
                {"id": "uuid", "action": "write"},
            ]
        },
        ...
    ]
    """
    services_result = await db.execute(
        select(ServiceGroup).order_by(ServiceGroup.name)
    )
    services = services_result.scalars().all()

    registry = []
    for svc in services:
        actions_result = await db.execute(
            select(ActionGroup)
            .where(ActionGroup.service_group_id == svc.id)
            .order_by(ActionGroup.action)
        )
        actions = actions_result.scalars().all()

        registry.append({
            "id": str(svc.id),
            "name": svc.name,
            "description": svc.description,
            "actions": [
                {"id": str(a.id), "action": a.action}
                for a in actions
            ],
        })

    return registry

