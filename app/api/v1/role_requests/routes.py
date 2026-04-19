from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.infrastructure.auth.repository import get_role_by_name
from app.role_utils import get_user_role_ids, get_user_role_names
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/role-requests", tags=["role-requests"])

VALID_REQUESTED_ROLES = {"broker", "owner"}


def _company_id_str(user: dict[str, Any]) -> str | None:
    cid = user.get("companyId")
    return str(cid) if cid else None


# ------------------------------------------------------------------ #
# POST /api/role-requests  — any authenticated user
# ------------------------------------------------------------------ #
@router.post("")
async def create_role_request(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    requested_role = (payload.get("requestedRole") or "").strip().lower()
    if requested_role not in VALID_REQUESTED_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"requestedRole must be one of: {', '.join(sorted(VALID_REQUESTED_ROLES))}",
        )

    reason = (payload.get("reason") or "").strip() or None
    user_id = str(user.get("id") or user.get("_id"))
    company_id = _company_id_str(user)

    db = get_db()

    # Prevent duplicate pending requests for the same role
    existing = await db["role_requests"].find_one(
        {
            "userId": user_id,
            "requestedRole": requested_role,
            "status": "pending",
        }
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"You already have a pending request for the '{requested_role}' role",
        )

    # Gather current role names for reference
    current_role_names = list(await get_user_role_names(user))
    current_role_ids = get_user_role_ids(user)

    now = datetime.now(timezone.utc)
    doc = {
        "userId": user_id,
        "userName": f"{user.get('firstName', '')} {user.get('lastName', '')}".strip(),
        "userEmail": user.get("email", ""),
        "requestedRole": requested_role,
        "currentRoles": current_role_names,
        "reason": reason,
        "status": "pending",
        "reviewedBy": None,
        "reviewedAt": None,
        "companyId": company_id,
        "createdAt": now,
        "updatedAt": now,
    }

    result = await db["role_requests"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


# ------------------------------------------------------------------ #
# GET /api/role-requests/my  — current user's own requests
# (must be registered BEFORE the parameterised /{request_id} route)
# ------------------------------------------------------------------ #
@router.get("/my")
async def my_role_requests(
    user: dict[str, Any] = Depends(get_current_user),
):
    user_id = str(user.get("id") or user.get("_id"))
    db = get_db()
    cursor = db["role_requests"].find({"userId": user_id}).sort("createdAt", -1)
    results = [serialize_doc(doc) async for doc in cursor]
    return {"results": results, "total": len(results)}


# ------------------------------------------------------------------ #
# GET /api/role-requests  — admin / super only, scoped by company
# ------------------------------------------------------------------ #
@router.get("")
async def list_role_requests(
    status: str = Query("pending"),
    user: dict[str, Any] = Depends(require_roles("admin")),
):
    user_roles = await get_user_role_names(user)
    is_super = "super" in user_roles
    company_id = _company_id_str(user)

    query: dict[str, Any] = {"status": status}
    if not is_super:
        if not company_id:
            return {"results": [], "total": 0}
        query["companyId"] = company_id

    db = get_db()
    cursor = db["role_requests"].find(query).sort("createdAt", -1)
    results = [serialize_doc(doc) async for doc in cursor]
    return {"results": results, "total": len(results)}


# ------------------------------------------------------------------ #
# PATCH /api/role-requests/{request_id}  — approve / reject (admin/super)
# ------------------------------------------------------------------ #
@router.patch("/{request_id}")
async def review_role_request(
    request_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(require_roles("admin")),
):
    new_status = (payload.get("status") or "").strip().lower()
    if new_status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="status must be 'approved' or 'rejected'",
        )

    db = get_db()

    try:
        req_oid = to_object_id(request_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request_id format")

    role_request = await db["role_requests"].find_one({"_id": req_oid})
    if not role_request:
        raise HTTPException(status_code=404, detail="Role request not found")

    if role_request.get("status") != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Request has already been {role_request['status']}",
        )

    # Company scoping: non-super admins can only review within their company
    user_roles = await get_user_role_names(user)
    is_super = "super" in user_roles
    if not is_super:
        admin_company = _company_id_str(user)
        if not admin_company or admin_company != role_request.get("companyId"):
            raise HTTPException(status_code=403, detail="Forbidden")

    reviewer_id = str(user.get("id") or user.get("_id"))
    now = datetime.now(timezone.utc)

    update_fields: dict[str, Any] = {
        "status": new_status,
        "reviewedBy": reviewer_id,
        "reviewedAt": now,
        "updatedAt": now,
    }

    # On approval — assign roles to the target user
    if new_status == "approved":
        target_user_id = role_request["userId"]
        requested_role = role_request["requestedRole"]

        # Resolve role IDs for the roles we need to assign
        roles_to_assign: set[str] = set()

        if requested_role == "broker":
            # Broker gets broker + owner roles
            for rname in ("broker", "owner"):
                role_doc = await get_role_by_name(rname)
                if role_doc:
                    roles_to_assign.add(str(role_doc["_id"]))
        elif requested_role == "owner":
            role_doc = await get_role_by_name("owner")
            if role_doc:
                roles_to_assign.add(str(role_doc["_id"]))

        if not roles_to_assign:
            raise HTTPException(
                status_code=500,
                detail="Could not resolve requested role(s) in the database",
            )

        # Fetch the target user to keep existing roles (multi-role)
        try:
            target_oid = to_object_id(target_user_id)
        except Exception:
            raise HTTPException(status_code=500, detail="Invalid target userId")

        target_user = await db["users"].find_one({"_id": target_oid})
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")

        # Merge: keep existing roleIds + add new ones
        existing_role_ids = set(get_user_role_ids(target_user))
        merged_role_ids = list(existing_role_ids | roles_to_assign)

        await db["users"].update_one(
            {"_id": target_oid},
            {"$set": {"roleIds": merged_role_ids, "updatedAt": now}},
        )

    await db["role_requests"].update_one(
        {"_id": req_oid},
        {"$set": update_fields},
    )

    updated = await db["role_requests"].find_one({"_id": req_oid})
    return serialize_doc(updated)
