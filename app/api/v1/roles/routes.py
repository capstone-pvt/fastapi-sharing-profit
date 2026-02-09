from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.deps import get_current_user, require_roles
from app.domain.roles.services import (
    build_create_role_payload,
    build_update_role_payload,
)
from app.infrastructure.roles.repository import (
    add_permissions as repo_add_permissions,
    create_role as repo_create_role,
    delete_role as repo_delete_role,
    get_role as repo_get_role,
    list_roles as repo_list_roles,
    remove_permissions as repo_remove_permissions,
    update_role as repo_update_role,
)


router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", dependencies=[Depends(get_current_user)])
async def list_roles():
    return await repo_list_roles()


@router.get("/{role_id}", dependencies=[Depends(get_current_user)])
async def get_role(role_id: str):
    doc = await repo_get_role(role_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    return doc


@router.post("", dependencies=[Depends(require_roles("admin"))])
async def create_role(payload: dict[str, Any] = Body(...)):
    role_payload = build_create_role_payload(payload)
    return await repo_create_role(role_payload)


@router.patch("/{role_id}", dependencies=[Depends(require_roles("admin"))])
async def update_role(role_id: str, payload: dict[str, Any] = Body(...)):
    doc = await repo_get_role(role_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    role_name = (doc.get("name") or "").strip().lower()
    # Canonical protected roles
    protected = {"admin", "super"}
    if role_name in protected:
        raise HTTPException(status_code=403, detail="Cannot modify protected role")
    role_payload = build_update_role_payload(payload)
    doc = await repo_update_role(role_id, role_payload)
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    return doc


@router.post("/{role_id}/permissions", dependencies=[Depends(require_roles("admin"))])
async def add_permissions(role_id: str, payload: dict[str, Any] = Body(...)):
    doc = await repo_get_role(role_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    role_name = (doc.get("name") or "").strip().lower()
    # Canonical protected roles
    protected = {"admin", "super"}
    if role_name in protected:
        raise HTTPException(status_code=403, detail="Cannot modify protected role")
    permissions = payload.get("permissions", [])
    doc = await repo_add_permissions(role_id, permissions)
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    return doc


@router.delete("/{role_id}/permissions", dependencies=[Depends(require_roles("admin"))])
async def remove_permissions(role_id: str, payload: dict[str, Any] = Body(...)):
    doc = await repo_get_role(role_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    role_name = (doc.get("name") or "").strip().lower()
    # Canonical protected roles
    protected = {"admin", "super"}
    if role_name in protected:
        raise HTTPException(status_code=403, detail="Cannot modify protected role")
    permissions = payload.get("permissions", [])
    doc = await repo_remove_permissions(role_id, permissions)
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    return doc


@router.delete("/{role_id}", dependencies=[Depends(require_roles("admin"))])
async def delete_role(role_id: str):
    doc = await repo_get_role(role_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    role_name = (doc.get("name") or "").strip().lower()
    # Canonical protected roles
    protected = {"admin", "super"}
    if role_name in protected:
        raise HTTPException(status_code=403, detail="Cannot delete protected role")
    deleted = await repo_delete_role(role_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"status": "deleted"}
