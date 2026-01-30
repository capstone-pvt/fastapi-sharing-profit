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


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", dependencies=[Depends(require_permissions("user:read"))])
async def list_users(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    search = request.query_params.get("search")
    query = build_user_query(search)
    results, total = await repo_list_users(query, limit=limit, offset=offset)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/{user_id}", dependencies=[Depends(require_permissions("user:read"))])
async def get_user(user_id: str):
    doc = await repo_get_user(user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
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
    if not payload.get("companyName") and user.get("companyName"):
        payload["companyName"] = user["companyName"]
    user_payload = build_create_user_payload(payload, hash_password=hash_password)
    return await repo_create_user(user_payload)


@router.patch("/{user_id}", dependencies=[Depends(require_permissions("user:update"))])
async def update_user(
    user_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    payload.pop("companyName", None)
    update_payload = build_update_user_payload(payload, hash_password=hash_password)
    doc = await repo_update_user(user_id, update_payload)
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return doc


@router.delete("/{user_id}", dependencies=[Depends(require_permissions("user:delete"))])
async def delete_user(user_id: str):
    deleted = await repo_delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted"}
