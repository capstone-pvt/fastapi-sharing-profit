"""Government-managed vessel verification.

PATCH ``/vessels/{vessel_id}/verification`` moves a vessel through the
regulator workflow (pending → verified → expired/rejected). Only users with
the ``government`` role can call it; brokers/owners/admins are blocked
because verification is a cross-company regulatory function.

The vessel document carries:
    verificationStatus: pending | verified | expired | rejected
    documentExpiresAt:  ISO date (license/permit expiry)
    verifiedBy:         user id (government regulator)
    verifiedByName:     display name
    verifiedAt:         timestamp of last status change
    verificationNotes:  free-form regulator note
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.deps import get_current_user
from app.db import get_db
from app.infrastructure.roles.repository import RoleNames, get_role
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/vessels", tags=["vessel-verification"])


_ALLOWED_STATUSES = {"pending", "verified", "expired", "rejected"}


async def _has_government_role(user: dict[str, Any]) -> bool:
    role_ids = list(user.get("roleIds") or [])
    if user.get("roleId"):
        role_ids.append(user["roleId"])
    for rid in role_ids:
        if not rid:
            continue
        role = await get_role(str(rid))
        if (
            role
            and (role.get("name") or "").strip().lower() == RoleNames.GOVERNMENT
        ):
            return True
    return False


@router.patch("/{vessel_id}/verification")
async def update_verification(
    vessel_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    if not await _has_government_role(user):
        raise HTTPException(
            status_code=403,
            detail="Only government regulators can update vessel verification.",
        )

    new_status = (payload.get("verificationStatus") or "").strip().lower()
    if new_status not in _ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"verificationStatus must be one of: {sorted(_ALLOWED_STATUSES)}",
        )

    db = get_db()
    try:
        oid = to_object_id(vessel_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Vessel not found")

    existing = await db["vessels"].find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Vessel not found")

    full_name = " ".join(
        p for p in [user.get("firstName"), user.get("lastName")] if p
    ).strip()
    now = datetime.now(timezone.utc)
    update_fields: dict[str, Any] = {
        "verificationStatus": new_status,
        "verifiedBy": str(user.get("_id") or user.get("id") or ""),
        "verifiedByName": full_name or user.get("email"),
        "verifiedAt": now,
        "updatedAt": now,
    }

    if "documentExpiresAt" in payload:
        raw_expiry = payload.get("documentExpiresAt")
        update_fields["documentExpiresAt"] = (
            str(raw_expiry).strip() if raw_expiry else None
        )
    if payload.get("verificationNotes") is not None:
        note = str(payload["verificationNotes"]).strip()
        update_fields["verificationNotes"] = note or None

    await db["vessels"].update_one({"_id": oid}, {"$set": update_fields})
    saved = await db["vessels"].find_one({"_id": oid})
    return serialize_doc(saved)
