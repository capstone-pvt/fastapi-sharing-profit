from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from app.core.security import hash_password
from app.deps import get_current_user, require_permissions
from app.domain.users.services import (
    build_create_user_payload,
    build_update_user_payload,
    build_user_query,
    validate_user_payload,
)
from app.infrastructure.users.repository import (
    create_user as repo_create_user,
    delete_user as repo_delete_user,
    get_user as repo_get_user,
    list_users as repo_list_users,
    update_user as repo_update_user,
)
from app.infrastructure.roles.repository import get_role
from app.infrastructure.auth.repository import get_role_by_name
from app.db import get_db
from app.utils import to_object_id


router = APIRouter(prefix="/users", tags=["users"])

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


async def _get_role_flags(user: dict[str, Any]) -> tuple[str, bool, bool]:
    role_name = (await _get_role_name(user)).strip().lower()
    is_super = role_name in SUPER_ROLE_NAMES
    is_company_admin = role_name in ADMIN_ROLE_NAMES
    return role_name, is_super, is_company_admin


def _company_id_value(data: dict[str, Any]) -> str | None:
    company_id = data.get("companyId")
    return str(company_id) if company_id else None


def _company_object_id(company_id: str | None) -> Any | None:
    if not company_id:
        return None
    try:
        return to_object_id(company_id)
    except Exception:
        return None


@router.get("", dependencies=[Depends(require_permissions("user:read"))])
async def list_users(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
):
    search = request.query_params.get("search")
    pending = request.query_params.get("pending", "").lower() in ("1", "true", "yes")
    query = build_user_query(search=search, pending=pending)
    _, is_super, is_company_admin = await _get_role_flags(user)
    if is_company_admin and not is_super:
        company_id = _company_id_value(user)
        object_id = _company_object_id(company_id)
        if not object_id:
            return {"results": [], "total": 0, "limit": limit, "offset": offset}
        query["companyId"] = object_id
    results, total = await repo_list_users(query, limit=limit, offset=offset)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/{user_id}", dependencies=[Depends(require_permissions("user:read"))])
async def get_user(
    user_id: str, user: dict[str, Any] = Depends(get_current_user)
):
    doc = await repo_get_user(user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    _, is_super, is_company_admin = await _get_role_flags(user)
    if is_company_admin and not is_super:
        company_id = _company_id_value(user)
        target_company_id = _company_id_value(doc)
        if not company_id or company_id != target_company_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    return doc


@router.post("", dependencies=[Depends(require_permissions("user:create"))])
async def create_user(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    required = ["email", "password", "firstName", "lastName", "roleId"]
    try:
        validate_user_payload(payload, required)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _, is_super, is_company_admin = await _get_role_flags(user)
    if is_company_admin and not is_super:
        company_id = _company_id_value(user)
        object_id = _company_object_id(company_id)
        if not object_id:
            raise HTTPException(status_code=403, detail="Company not set for admin")
        payload["companyId"] = object_id
        if user.get("companyName"):
            payload["companyName"] = user["companyName"]
    elif payload.get("companyId"):
        object_id = _company_object_id(str(payload["companyId"]))
        if not object_id:
            raise HTTPException(status_code=400, detail="Invalid companyId")
        payload["companyId"] = object_id
    if not payload.get("companyName") and user.get("companyName"):
        payload["companyName"] = user["companyName"]
    if payload.get("email") and payload["email"].strip().lower() == user.get("email", "").lower():
        raise HTTPException(status_code=400, detail="Cannot create your own account")
    role_id = payload.get("roleId")
    if role_id:
        role = await get_role(role_id)
        role_name = role.get("name") if role else None
        if role_name and role_name.lower() in {"admin", "super"}:
            raise HTTPException(status_code=403, detail="Cannot assign admin roles")
    if role_id and payload.get("companyName"):
        db = get_db()
        name = payload.get("companyName", "").strip()
        if name:
            await db["companies"].update_one(
                {"companyName": {"$regex": f"^{name}$", "$options": "i"}},
                {
                    "$setOnInsert": {
                        "companyName": name,
                        "companyAddress": payload.get("companyAddress"),
                        "companyPhone": payload.get("companyPhone"),
                        "companyTaxId": payload.get("companyTaxId"),
                    }
                },
                upsert=True,
            )
    user_payload = build_create_user_payload(payload, hash_password=hash_password)
    return await repo_create_user(user_payload)


@router.patch("/{user_id}", dependencies=[Depends(require_permissions("user:update"))])
async def update_user(
    user_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    target_user = await repo_get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    _, is_super, is_company_admin = await _get_role_flags(user)
    is_admin = is_super or is_company_admin
    if is_company_admin and not is_super:
        company_id = _company_id_value(user)
        target_company_id = _company_id_value(target_user)
        if not company_id or company_id != target_company_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        payload.pop("companyId", None)
    if not is_admin:
        payload.pop("companyName", None)
        payload.pop("companyAddress", None)
        payload.pop("companyPhone", None)
        payload.pop("companyTaxId", None)
        payload.pop("companyApproved", None)  # Only admins can approve registration
    if is_admin and payload.get("companyApproved") is True:
        crew_role = await get_role_by_name("crew")
        if crew_role:
            payload["roleId"] = str(crew_role["_id"])
    if is_admin and payload.get("companyName"):
        db = get_db()
        name = payload.get("companyName", "").strip()
        if name:
            await db["companies"].update_one(
                {"companyName": {"$regex": f"^{name}$", "$options": "i"}},
                {
                    "$setOnInsert": {
                        "companyName": name,
                        "companyAddress": payload.get("companyAddress"),
                        "companyPhone": payload.get("companyPhone"),
                        "companyTaxId": payload.get("companyTaxId"),
                    }
                },
                upsert=True,
            )
    update_payload = build_update_user_payload(payload, hash_password=hash_password)
    doc = await repo_update_user(user_id, update_payload)
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return doc


@router.delete("/{user_id}", dependencies=[Depends(require_permissions("user:delete"))])
async def delete_user(
    user_id: str, user: dict[str, Any] = Depends(get_current_user)
):
    target_user = await repo_get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    _, is_super, is_company_admin = await _get_role_flags(user)
    if is_company_admin and not is_super:
        company_id = _company_id_value(user)
        target_company_id = _company_id_value(target_user)
        if not company_id or company_id != target_company_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    deleted = await repo_delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted"}
