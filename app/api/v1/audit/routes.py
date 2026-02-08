"""
Audit log API endpoints.
Allows administrators to view audit logs for company assignments and other actions.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.deps import get_current_user, require_permissions
from app.infrastructure.audit.repository import (
    list_audit_logs,
    get_audit_log,
    get_user_audit_history,
    get_company_audit_history
)
from app.infrastructure.roles.repository import get_role


router = APIRouter(prefix="/audit-logs", tags=["audit"])

SUPER_ROLE_NAMES = {"super", "superadmin", "super admin", "super-admin"}
ADMIN_ROLE_NAMES = {"admin", "system admin"}


async def _get_role_name(user: dict[str, Any]) -> str:
    role_value = user.get("role")
    if isinstance(role_value, dict):
        role_name = role_value.get("name")
        if role_name:
            return str(role_name)
        role_value = role_value.get("id")
    if not role_value:
        role_value = user.get("roleId")
    if not role_value:
        return ""
    role = await get_role(str(role_value))
    return str(role.get("name") or "") if role else ""


async def _is_admin(user: dict[str, Any]) -> bool:
    role_name = (await _get_role_name(user)).strip().lower()
    return role_name in SUPER_ROLE_NAMES or role_name in ADMIN_ROLE_NAMES


@router.get("", dependencies=[Depends(require_permissions("audit:read"))])
async def list_audit(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
):
    """
    List audit logs with filtering options.
    Only admins and super admins can access audit logs.
    """
    if not await _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")

    query: dict[str, Any] = {}

    if action:
        query["action"] = action

    if entity_type:
        query["entityType"] = entity_type

    if entity_id:
        query["entityId"] = entity_id

    results, total = await list_audit_logs(query, limit=limit, offset=offset)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/{audit_id}", dependencies=[Depends(require_permissions("audit:read"))])
async def get_audit(
    audit_id: str,
    user: dict[str, Any] = Depends(get_current_user)
):
    """
    Get a single audit log by ID.
    Only admins and super admins can access audit logs.
    """
    if not await _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")

    doc = await get_audit_log(audit_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Audit log not found")

    return doc


@router.get("/user/{user_id}", dependencies=[Depends(require_permissions("audit:read"))])
async def get_user_audit(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
):
    """
    Get audit history for a specific user.
    Only admins and super admins can access audit logs.
    """
    if not await _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")

    results, total = await get_user_audit_history(
        user_id,
        action_filter=action,
        limit=limit,
        offset=offset
    )

    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/company/{company_id}", dependencies=[Depends(require_permissions("audit:read"))])
async def get_company_audit(
    company_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
):
    """
    Get audit history for a specific company.
    Only admins and super admins can access audit logs.
    """
    if not await _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")

    results, total = await get_company_audit_history(
        company_id,
        limit=limit,
        offset=offset
    )

    return {"results": results, "total": total, "limit": limit, "offset": offset}
