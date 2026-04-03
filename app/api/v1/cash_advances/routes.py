from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.db import get_db
from app.deps import get_current_user, require_permissions
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/cash-advances", tags=["cash-advances"])


@router.patch("/{item_id}/approve", dependencies=[Depends(require_permissions("cash-advances:approve"))])
async def approve_cash_advance(
    item_id: str,
    payload: dict[str, Any] = Body(default={}),
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_db()
    update_payload: dict[str, Any] = {
        "status": "approved",
        "approvedBy": user["id"],
        "approvedDate": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    if isinstance(payload, dict) and payload.get("notes") is not None:
        update_payload["notes"] = payload["notes"]

    await db["cash_advances"].update_one(
        {"_id": to_object_id(item_id)}, {"$set": update_payload}
    )
    doc = await db["cash_advances"].find_one({"_id": to_object_id(item_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return serialize_doc(doc)


@router.patch("/{item_id}/decline", dependencies=[Depends(require_permissions("cash-advances:decline"))])
async def decline_cash_advance(
    item_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    decline_reason = payload.get("declineReason") if isinstance(payload, dict) else None
    if not decline_reason:
        raise HTTPException(status_code=400, detail="declineReason is required")

    db = get_db()
    update_payload = {
        "status": "declined",
        "declineReason": decline_reason,
        "declinedDate": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    if isinstance(payload, dict) and payload.get("notes") is not None:
        update_payload["notes"] = payload["notes"]

    await db["cash_advances"].update_one(
        {"_id": to_object_id(item_id)}, {"$set": update_payload}
    )
    doc = await db["cash_advances"].find_one({"_id": to_object_id(item_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return serialize_doc(doc)
