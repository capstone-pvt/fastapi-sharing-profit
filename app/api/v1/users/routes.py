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
from app.infrastructure.audit.repository import log_company_assignment
from app.db import get_db
from app.utils import escape_regex, to_object_id


router = APIRouter(prefix="/users", tags=["users"])

# Canonical role names: super | admin | broker | owner | crew | user
SUPER_ROLE_NAMES = {"super"}
ADMIN_ROLE_NAMES = {"admin"}


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
    _, is_super, _ = await _get_role_flags(user)
    if not is_super:
        company_id = _company_id_value(user)
        object_id = _company_object_id(company_id)
        if not object_id:
            return {"results": [], "total": 0, "limit": limit, "offset": offset}
        # Match both ObjectId and string stored companyId (legacy compat)
        query["companyId"] = {"$in": [object_id, str(object_id)]}
    results, total = await repo_list_users(query, limit=limit, offset=offset)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/pending-approvals")
async def list_pending_approvals(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
):
    """Return the pending users the caller can actually approve.

    Auth-only (no user:read permission required) so that delegates can hit it.
    Scope:
      - super admin: all pending users everywhere
      - company admin: all pending users in their company
      - delegate: pending users in their company whose ``requestedRole`` is in
        the caller's ``approvalDelegates``
      - anyone else: empty list
    """
    _, is_super, is_company_admin = await _get_role_flags(user)
    is_admin = is_super or is_company_admin
    delegates_current = [
        r.strip().lower()
        for r in (user.get("approvalDelegates") or [])
        if isinstance(r, str) and r.strip()
    ]

    if not is_admin and not delegates_current:
        return {"results": [], "total": 0, "limit": limit, "offset": offset}

    query: dict[str, Any] = {"companyApproved": False}
    if not is_super:
        company_id = _company_id_value(user)
        object_id = _company_object_id(company_id)
        if not object_id:
            return {"results": [], "total": 0, "limit": limit, "offset": offset}
        query["companyId"] = {"$in": [object_id, str(object_id)]}
    if not is_admin:
        # Delegate scope: only matching requested roles.
        query["requestedRole"] = {"$in": delegates_current}

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
                {"companyName": {"$regex": f"^{escape_regex(name)}$", "$options": "i"}},
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
            # Get the company _id and set it in the payload
            company = await db["companies"].find_one(
                {"companyName": {"$regex": f"^{escape_regex(name)}$", "$options": "i"}}
            )
            if company:
                payload["companyId"] = company["_id"]
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

    # Is the caller a delegate who can approve *this* pending registration?
    delegates_current = [
        r.strip().lower()
        for r in (user.get("approvalDelegates") or [])
        if isinstance(r, str) and r.strip()
    ]
    target_requested_role = (
        str(target_user.get("requestedRole") or "").strip().lower() or None
    )
    is_delegate_for_target = (
        not is_admin
        and bool(target_requested_role)
        and target_requested_role in delegates_current
        and _company_id_value(user) is not None
        and _company_id_value(user) == _company_id_value(target_user)
    )

    # Prevent super users from editing their own account
    current_user_id = str(user.get("id") or user.get("_id"))
    if is_super and user_id == current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Super users cannot edit their own account"
        )
    if is_company_admin and not is_super:
        company_id = _company_id_value(user)
        target_company_id = _company_id_value(target_user)
        if not company_id or company_id != target_company_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        payload.pop("companyId", None)

    # `approvalDelegates` is admin-only — strip for everyone else.
    if not is_admin and "approvalDelegates" in payload:
        payload.pop("approvalDelegates", None)
    # Validate + normalise when admin sets it.
    if is_admin and "approvalDelegates" in payload:
        raw = payload.get("approvalDelegates") or []
        if not isinstance(raw, list):
            raise HTTPException(
                status_code=400, detail="approvalDelegates must be a list of role names"
            )
        payload["approvalDelegates"] = [
            r.strip().lower()
            for r in raw
            if isinstance(r, str) and r.strip()
        ]

    if not is_admin:
        payload.pop("companyName", None)
        payload.pop("companyAddress", None)
        payload.pop("companyPhone", None)
        payload.pop("companyTaxId", None)
        # Delegates can approve for their authorised role; strip otherwise.
        if not is_delegate_for_target:
            payload.pop("companyApproved", None)

    if (is_admin or is_delegate_for_target) and payload.get("companyApproved") is True:
        # Promote the approved user to their requested role (e.g. broker/owner).
        # Fall back to "crew" when no explicit request was captured.
        desired_role_name = target_requested_role or "crew"
        desired_role = await get_role_by_name(desired_role_name)
        if not desired_role and desired_role_name != "crew":
            # Unknown role → fall back to crew so the approval still succeeds.
            desired_role = await get_role_by_name("crew")
        if desired_role:
            payload["roleIds"] = [str(desired_role["_id"])]
    if is_admin and payload.get("companyName"):
        db = get_db()
        name = payload.get("companyName", "").strip()
        if name:
            result = await db["companies"].update_one(
                {"companyName": {"$regex": f"^{escape_regex(name)}$", "$options": "i"}},
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
            # Get the company _id and set it in the payload
            company = await db["companies"].find_one(
                {"companyName": {"$regex": f"^{escape_regex(name)}$", "$options": "i"}}
            )
            if company:
                payload["companyId"] = company["_id"]
    update_payload = build_update_user_payload(payload, hash_password=hash_password)
    doc = await repo_update_user(user_id, update_payload)
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return doc


@router.post("/{user_id}/approve")
async def approve_user(
    user_id: str,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Approve a pending user.

    Caller may be: super admin, company admin, or a company member whose
    ``approvalDelegates`` array contains the target's ``requestedRole``.

    On success the target's ``companyApproved`` flips to ``True`` and their
    role is promoted from the default "user" placeholder to the role they
    requested during signup (falling back to "crew" if unknown).
    """
    target_user = await repo_get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    _, is_super, is_company_admin = await _get_role_flags(user)
    is_admin = is_super or is_company_admin

    target_requested_role = (
        str(target_user.get("requestedRole") or "").strip().lower() or None
    )
    delegates_current = [
        r.strip().lower()
        for r in (user.get("approvalDelegates") or [])
        if isinstance(r, str) and r.strip()
    ]
    is_delegate_for_target = (
        not is_admin
        and bool(target_requested_role)
        and target_requested_role in delegates_current
    )

    # Scope check: everyone (admin or delegate) must share the company with the target.
    if not is_super:
        caller_company = _company_id_value(user)
        target_company = _company_id_value(target_user)
        if not caller_company or caller_company != target_company:
            raise HTTPException(status_code=403, detail="Forbidden")

    if not (is_admin or is_delegate_for_target):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to approve this registration",
        )

    update_payload: dict[str, Any] = {"companyApproved": True}
    desired_role_name = target_requested_role or "crew"
    desired_role = await get_role_by_name(desired_role_name)
    if not desired_role and desired_role_name != "crew":
        desired_role = await get_role_by_name("crew")
    if desired_role:
        update_payload["roleIds"] = [str(desired_role["_id"])]

    payload = build_update_user_payload(update_payload, hash_password=hash_password)
    doc = await repo_update_user(user_id, payload)
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return doc


@router.post("/{user_id}/reject")
async def reject_user(
    user_id: str,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Reject a pending registration.

    Same authorisation surface as approve. Deletes the pending user record.
    """
    target_user = await repo_get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    _, is_super, is_company_admin = await _get_role_flags(user)
    is_admin = is_super or is_company_admin

    target_requested_role = (
        str(target_user.get("requestedRole") or "").strip().lower() or None
    )
    delegates_current = [
        r.strip().lower()
        for r in (user.get("approvalDelegates") or [])
        if isinstance(r, str) and r.strip()
    ]
    is_delegate_for_target = (
        not is_admin
        and bool(target_requested_role)
        and target_requested_role in delegates_current
    )

    if not is_super:
        caller_company = _company_id_value(user)
        target_company = _company_id_value(target_user)
        if not caller_company or caller_company != target_company:
            raise HTTPException(status_code=403, detail="Forbidden")

    if not (is_admin or is_delegate_for_target):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to reject this registration",
        )

    deleted = await repo_delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "rejected"}


@router.delete("/{user_id}", dependencies=[Depends(require_permissions("user:delete"))])
async def delete_user(
    user_id: str, user: dict[str, Any] = Depends(get_current_user)
):
    target_user = await repo_get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    _, is_super, is_company_admin = await _get_role_flags(user)

    # Prevent super users from deleting their own account
    current_user_id = str(user.get("id") or user.get("_id"))
    if is_super and user_id == current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Super users cannot delete their own account"
        )

    if is_company_admin and not is_super:
        company_id = _company_id_value(user)
        target_company_id = _company_id_value(target_user)
        if not company_id or company_id != target_company_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    deleted = await repo_delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted"}


@router.post("/bulk-assign-company", dependencies=[Depends(require_permissions("user:update"))])
async def bulk_assign_company(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    """
    Bulk assign a company to multiple users.
    Only super admins can use this endpoint.

    Payload:
    {
        "userIds": ["user_id_1", "user_id_2", ...],
        "companyId": "company_id"
    }
    """
    _, is_super, is_company_admin = await _get_role_flags(user)

    if not is_super:
        raise HTTPException(
            status_code=403,
            detail="Only super admins can perform bulk company assignments"
        )

    user_ids = payload.get("userIds", [])
    company_id = payload.get("companyId")

    if not user_ids or not isinstance(user_ids, list):
        raise HTTPException(status_code=400, detail="userIds must be a non-empty array")

    if not company_id:
        raise HTTPException(status_code=400, detail="companyId is required")

    db = get_db()
    try:
        company_object_id = to_object_id(company_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid companyId format")

    company = await db["companies"].find_one({"_id": company_object_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    success_count = 0
    failed_users = []
    updated_users = []

    for user_id in user_ids:
        try:
            target_user = await repo_get_user(user_id)
            if not target_user:
                failed_users.append({"userId": user_id, "reason": "User not found"})
                continue

            update_payload = {
                "companyId": company_object_id,
                "companyName": company.get("companyName"),
                "companyAddress": company.get("companyAddress"),
                "companyPhone": company.get("companyPhone"),
                "companyTaxId": company.get("companyTaxId"),
            }

            doc = await repo_update_user(user_id, update_payload)
            if doc:
                success_count += 1
                updated_users.append({
                    "userId": user_id,
                    "email": doc.get("email"),
                    "companyName": doc.get("companyName")
                })
            else:
                failed_users.append({"userId": user_id, "reason": "Update failed"})
        except Exception as e:
            failed_users.append({"userId": user_id, "reason": str(e)})

    return {
        "status": "completed",
        "totalRequested": len(user_ids),
        "successCount": success_count,
        "failedCount": len(failed_users),
        "updatedUsers": updated_users,
        "failedUsers": failed_users,
        "companyAssigned": {
            "id": company_id,
            "name": company.get("companyName")
        }
    }
