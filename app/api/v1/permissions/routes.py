from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.deps import get_current_user, require_roles
from app.domain.permissions.services import (
    build_create_permission_payload,
    build_update_permission_payload,
)
from app.infrastructure.permissions.repository import (
    create_permission as repo_create_permission,
    delete_permission as repo_delete_permission,
    get_permission as repo_get_permission,
    list_permissions as repo_list_permissions,
    update_permission as repo_update_permission,
)


router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("", dependencies=[Depends(get_current_user)])
async def list_permissions():
    return await repo_list_permissions()


@router.get("/{perm_id}", dependencies=[Depends(get_current_user)])
async def get_permission(perm_id: str):
    doc = await repo_get_permission(perm_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Permission not found")
    return doc


@router.post("", dependencies=[Depends(require_roles("admin"))])
async def create_permission(payload: dict[str, Any] = Body(...)):
    perm_payload = build_create_permission_payload(payload)
    return await repo_create_permission(perm_payload)


@router.patch("/{perm_id}", dependencies=[Depends(require_roles("admin"))])
async def update_permission(perm_id: str, payload: dict[str, Any] = Body(...)):
    perm_payload = build_update_permission_payload(payload)
    doc = await repo_update_permission(perm_id, perm_payload)
    if not doc:
        raise HTTPException(status_code=404, detail="Permission not found")
    return doc


@router.delete("/{perm_id}", dependencies=[Depends(require_roles("admin"))])
async def delete_permission(perm_id: str):
    deleted = await repo_delete_permission(perm_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Permission not found")
    return {"status": "deleted"}
