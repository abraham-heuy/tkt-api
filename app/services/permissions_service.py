"""
Permission service -- the AWS-IAM-style access matrix.

has_permission is the single check every protected manager route runs.
super_admin always short-circuits to True; a manager needs a matching
row in manager_permissions joined through action_groups to a named
service_group + action.
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_group import ActionGroup
from app.models.manager_permission import ManagerPermission
from app.models.Role import RoleName
from app.models.service_group import ServiceGroup


async def has_permission(
    db: AsyncSession, user_id: uuid.UUID, role_name: str, service_name: str, action: str
) -> bool:
    if role_name == RoleName.SUPER_ADMIN:
        return True
    if role_name != RoleName.MANAGER:
        return False

    stmt = (
        select(ManagerPermission.id)
        .join(ActionGroup, ActionGroup.id == ManagerPermission.action_group_id)
        .join(ServiceGroup, ServiceGroup.id == ActionGroup.service_group_id)
        .where(
            ManagerPermission.user_id == user_id,
            ServiceGroup.name == service_name,
            ActionGroup.action == action,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def list_permissions_for_manager(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """Return the flat list of (service_group, action) a manager can see -- used to grey out locked services on the console."""
    stmt = (
        select(ServiceGroup.name, ActionGroup.action)
        .join(ActionGroup, ActionGroup.service_group_id == ServiceGroup.id)
        .join(ManagerPermission, ManagerPermission.action_group_id == ActionGroup.id)
        .where(ManagerPermission.user_id == user_id)
    )
    result = await db.execute(stmt)
    return [{"service_group": row[0], "action": row[1]} for row in result.all()]


async def grant_permissions(
    db: AsyncSession,
    manager_id: uuid.UUID,
    action_group_ids: list[uuid.UUID],
    granted_by: uuid.UUID,
) -> None:
    for action_group_id in action_group_ids:
        db.add(
            ManagerPermission(
                user_id=manager_id, action_group_id=action_group_id, granted_by=granted_by
            )
        )
    await db.commit()


async def create_service_group(
    db: AsyncSession, name: str, description: str
) -> ServiceGroup:
    """Create a new service group."""
    service = ServiceGroup(name=name, description=description)
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


async def update_service_group(
    db: AsyncSession, service_id: uuid.UUID, name: str, description: str
) -> ServiceGroup:
    """Update service group name/description."""
    service = await db.get(ServiceGroup, service_id)
    if service is None:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, "service group not found")
    service.name = name
    service.description = description
    await db.commit()
    await db.refresh(service)
    return service


async def delete_service_group(db: AsyncSession, service_id: uuid.UUID) -> None:
    """Delete a service group and its associated action groups."""
    service = await db.get(ServiceGroup, service_id)
    if service is None:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, "service group not found")

    # Delete associated action groups and manager permissions manually
    # (or rely on cascade if configured; this is safe)
    action_ids = await db.execute(
        select(ActionGroup.id).where(ActionGroup.service_group_id == service_id)
    )
    ids = [row[0] for row in action_ids.all()]
    if ids:
        await db.execute(
            delete(ManagerPermission).where(ManagerPermission.action_group_id.in_(ids))
        )
        await db.execute(delete(ActionGroup).where(ActionGroup.id.in_(ids)))

    await db.delete(service)
    await db.commit()


async def add_action_group(
    db: AsyncSession, service_id: uuid.UUID, action: str
) -> ActionGroup:
    """Add a new action to a service group."""
    service = await db.get(ServiceGroup, service_id)
    if service is None:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, "service group not found")

    # Check duplicate
    existing = await db.execute(
        select(ActionGroup).where(
            ActionGroup.service_group_id == service_id,
            ActionGroup.action == action,
        )
    )
    if existing.scalar_one_or_none() is not None:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_409_CONFLICT, "action already exists")

    action_group = ActionGroup(service_group_id=service_id, action=action)
    db.add(action_group)
    await db.commit()
    await db.refresh(action_group)
    return action_group


async def delete_action_group(
    db: AsyncSession, service_id: uuid.UUID, action_group_id: uuid.UUID
) -> None:
    """Delete an action group and revoke associated permissions."""
    action_group = await db.get(ActionGroup, action_group_id)
    if action_group is None or action_group.service_group_id != service_id:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, "action group not found")

    # Delete manager permissions referencing this action
    await db.execute(
        delete(ManagerPermission).where(ManagerPermission.action_group_id == action_group_id)
    )
    await db.delete(action_group)
    await db.commit()    