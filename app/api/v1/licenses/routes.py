"""License / activation-code management endpoints.

Collection: ``app_licenses``

Document schema::

    {
        "activationCode": "XXXX-XXXX-XXXX-XXXX",
        "status": "active" | "expired" | "revoked",
        "companyId": ObjectId | null,
        "companyName": str | null,
        "activatedAt": datetime | null,
        "expiresAt": datetime | null,
        "maxUsers": int,
        "plan": "trial" | "standard" | "premium",
        "createdBy": str,
        "createdAt": datetime,
        "updatedAt": datetime,
    }
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any

from bson.errors import InvalidId
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.db import get_db
from app.deps import get_current_user
from app.infrastructure.roles.repository import get_role
from app.utils import serialize_doc, to_object_id

router = APIRouter(prefix="/licenses", tags=["licenses"])

SUPER_ROLE_NAMES = {"super"}
ADMIN_ROLE_NAMES = {"admin"}
COLLECTION = "app_licenses"


# ── helpers ──────────────────────────────────────────────────────────

def _generate_code() -> str:
    """Generate a human-readable activation code like ``ABCD-1234-EFGH-5678``."""
    chars = string.ascii_uppercase + string.digits
    segment = lambda: "".join(secrets.choice(chars) for _ in range(4))
    return f"{segment()}-{segment()}-{segment()}-{segment()}"


async def _role_name(user: dict[str, Any]) -> str:
    role_value = user.get("role")
    if isinstance(role_value, dict):
        name = role_value.get("name")
        if name:
            return str(name).strip().lower()
        role_value = role_value.get("id")
    if not role_value:
        role_value = user.get("roleId")
    if not role_value:
        return ""
    role = await get_role(str(role_value))
    return str(role.get("name") or "").strip().lower() if role else ""


async def _require_super(user: dict[str, Any]) -> None:
    if (await _role_name(user)) not in SUPER_ROLE_NAMES:
        raise HTTPException(status_code=403, detail="Super admin access required")


async def _require_admin_or_super(user: dict[str, Any]) -> None:
    if (await _role_name(user)) not in SUPER_ROLE_NAMES | ADMIN_ROLE_NAMES:
        raise HTTPException(status_code=403, detail="Admin access required")


# ── public: validate / activate ──────────────────────────────────────

@router.post("/validate")
async def validate_activation_code(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Validate and activate a license code for the user's company."""
    code = (payload.get("activationCode") or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="activationCode is required")

    db = get_db()
    doc = await db[COLLECTION].find_one({"activationCode": code})
    if not doc:
        raise HTTPException(status_code=422, detail="Invalid activation code. Please check and try again.")

    status = doc.get("status", "")
    if status == "revoked":
        raise HTTPException(status_code=400, detail="This activation code has been revoked")
    if status == "expired" or (doc.get("expiresAt") and doc["expiresAt"] < datetime.now(timezone.utc)):
        raise HTTPException(status_code=400, detail="This activation code has expired")
    if status == "active" and doc.get("companyId"):
        raise HTTPException(status_code=400, detail="This activation code is already in use")

    # Bind to user's company
    company_id = user.get("companyId")
    company_name = None
    if company_id:
        company = await db["companies"].find_one({"_id": to_object_id(str(company_id))})
        company_name = company.get("companyName") if company else None

    now = datetime.now(timezone.utc)
    expires_at = doc.get("expiresAt")
    if not expires_at:
        # Default: 1 year from activation
        duration_days = {"trial": 30, "standard": 365, "premium": 365}.get(
            doc.get("plan", "standard"), 365
        )
        expires_at = now + timedelta(days=duration_days)

    await db[COLLECTION].update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "status": "active",
                "companyId": to_object_id(str(company_id)) if company_id else None,
                "companyName": company_name,
                "activatedAt": now,
                "expiresAt": expires_at,
                "updatedAt": now,
            }
        },
    )
    updated = await db[COLLECTION].find_one({"_id": doc["_id"]})
    return serialize_doc(updated)


@router.get("/status")
async def get_license_status(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the license status for the current user's company."""
    db = get_db()
    rname = await _role_name(user)

    # Super users always have access
    if rname in SUPER_ROLE_NAMES:
        return {
            "hasLicense": True,
            "status": "active",
            "plan": "premium",
            "expiresAt": None,
            "isSuper": True,
        }

    company_id = user.get("companyId")
    if not company_id:
        return {"hasLicense": False, "status": "none", "plan": None, "expiresAt": None}

    try:
        oid = to_object_id(str(company_id))
    except InvalidId:
        return {"hasLicense": False, "status": "none", "plan": None, "expiresAt": None}

    license_doc = await db[COLLECTION].find_one(
        {"companyId": oid, "status": "active"},
        sort=[("expiresAt", -1)],
    )

    if not license_doc:
        return {"hasLicense": False, "status": "none", "plan": None, "expiresAt": None}

    expires_at = license_doc.get("expiresAt")
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        await db[COLLECTION].update_one(
            {"_id": license_doc["_id"]},
            {"$set": {"status": "expired", "updatedAt": datetime.now(timezone.utc)}},
        )
        return {
            "hasLicense": False,
            "status": "expired",
            "plan": license_doc.get("plan"),
            "expiresAt": expires_at.isoformat() if expires_at else None,
        }

    return {
        "hasLicense": True,
        "status": "active",
        "plan": license_doc.get("plan"),
        "expiresAt": expires_at.isoformat() if expires_at else None,
        "maxUsers": license_doc.get("maxUsers"),
        "activationCode": license_doc.get("activationCode"),
    }


# ── super-admin: generate / list / revoke ────────────────────────────

@router.post("/generate")
async def generate_license(
    payload: dict[str, Any] = Body({}),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate a new activation code (super admin only)."""
    await _require_super(user)

    plan = (payload.get("plan") or "standard").strip().lower()
    if plan not in ("trial", "standard", "premium"):
        raise HTTPException(status_code=400, detail="Plan must be trial, standard, or premium")

    max_users = int(payload.get("maxUsers", 20))
    duration_days = int(payload.get("durationDays", 365 if plan != "trial" else 30))

    db = get_db()
    now = datetime.now(timezone.utc)
    code = _generate_code()

    # Ensure uniqueness
    while await db[COLLECTION].find_one({"activationCode": code}):
        code = _generate_code()

    doc = {
        "activationCode": code,
        "status": "pending",
        "companyId": None,
        "companyName": None,
        "activatedAt": None,
        "expiresAt": None,
        "durationDays": duration_days,
        "maxUsers": max_users,
        "plan": plan,
        "createdBy": str(user.get("_id", user.get("id", ""))),
        "createdAt": now,
        "updatedAt": now,
    }
    result = await db[COLLECTION].insert_one(doc)
    created = await db[COLLECTION].find_one({"_id": result.inserted_id})
    return serialize_doc(created)


@router.get("")
async def list_licenses(
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """List all licenses (super admin only)."""
    await _require_super(user)

    db = get_db()
    query: dict[str, Any] = {}
    if status:
        query["status"] = status

    cursor = (
        db[COLLECTION]
        .find(query)
        .sort("createdAt", -1)
        .skip(offset)
        .limit(limit)
    )
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db[COLLECTION].count_documents(query)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.patch("/{license_id}/revoke")
async def revoke_license(
    license_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Revoke a license (super admin only)."""
    await _require_super(user)

    db = get_db()
    try:
        oid = to_object_id(license_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="License not found")

    result = await db[COLLECTION].update_one(
        {"_id": oid},
        {"$set": {"status": "revoked", "updatedAt": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="License not found")

    doc = await db[COLLECTION].find_one({"_id": oid})
    return serialize_doc(doc)
