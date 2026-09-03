"""Permission router — IAM service groups, actions, and grants."""

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete

from app.core.deps import AdminUser, AsyncDB, StaffUser
from app.core.service_registry import get_full_registry
from app.models.manager_permission import ManagerPermission
from app.services import permissions_service as permission_service

router = APIRouter()


# Request schema for creating/updating service
class ServiceCreateRequest(BaseModel):
    name: str
    description: str = ""


class ServiceUpdateRequest(BaseModel):
    name: str
    description: str = ""


class ActionCreateRequest(BaseModel):
    action: str


class GrantRequest(BaseModel):
    action_group_ids: list[uuid.UUID]


# ── Registry management (SuperAdmin only) ─────────────────────
@router.post("/services", status_code=201)
async def create_service(
    body: ServiceCreateRequest,
    current_user: AdminUser,
    db: AsyncDB,
):
    """Create a new service group."""
    _, _ = current_user
    return await permission_service.create_service_group(
        db, body.name, body.description
    )


@router.put("/services/{service_id}")
async def update_service(
    service_id: uuid.UUID,
    body: ServiceUpdateRequest,
    current_user: AdminUser,
    db: AsyncDB,
):
    """Update a service group name/description."""
    _, _ = current_user
    return await permission_service.update_service_group(
        db, service_id, body.name, body.description
    )


@router.delete("/services/{service_id}", status_code=204)
async def delete_service(
    service_id: uuid.UUID,
    current_user: AdminUser,
    db: AsyncDB,
):
    """Delete a service group and all associated actions."""
    _, _ = current_user
    await permission_service.delete_service_group(db, service_id)


@router.post("/services/{service_id}/actions", status_code=201)
async def add_action(
    service_id: uuid.UUID,
    body: ActionCreateRequest,
    current_user: AdminUser,
    db: AsyncDB,
):
    """Add a new action to a service group."""
    _, _ = current_user
    return await permission_service.add_action_group(db, service_id, body.action)


@router.delete("/services/{service_id}/actions/{action_group_id}", status_code=204)
async def delete_action(
    service_id: uuid.UUID,
    action_group_id: uuid.UUID,
    current_user: AdminUser,
    db: AsyncDB,
):
    """Delete an action group and revoke associated permissions."""
    _, _ = current_user
    await permission_service.delete_action_group(db, service_id, action_group_id)


# ── Existing endpoints (read / grant / revoke) ─────────────────

@router.get("/services")
async def list_services(
    current_user: StaffUser,
    db: AsyncDB,
):
    return await get_full_registry(db)


@router.get("/users/{user_id}")
async def get_user_permissions(
    user_id: uuid.UUID,
    current_user: StaffUser,
    db: AsyncDB,
):
    _, _ = current_user
    perms = await permission_service.list_permissions_for_manager(db, user_id)
    return {"user_id": str(user_id), "permissions": perms}


@router.post("/users/{user_id}", status_code=201)
async def grant_permissions(
    user_id: uuid.UUID,
    body: GrantRequest,
    current_user: AdminUser,
    db: AsyncDB,
):
    user, _ = current_user
    await permission_service.grant_permissions(
        db,
        manager_id=user_id,
        action_group_ids=body.action_group_ids,
        granted_by=user.id,
    )
    perms = await permission_service.list_permissions_for_manager(db, user_id)
    return {"user_id": str(user_id), "permissions": perms}


@router.delete("/users/{user_id}/{action_group_id}", status_code=204)
async def revoke_permission(
    user_id: uuid.UUID,
    action_group_id: uuid.UUID,
    current_user: AdminUser,
    db: AsyncDB,
):
    stmt = delete(ManagerPermission).where(
        ManagerPermission.user_id == user_id,
        ManagerPermission.action_group_id == action_group_id,
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission grant not found",
        )