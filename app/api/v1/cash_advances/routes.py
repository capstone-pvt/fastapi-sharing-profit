from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from bson.errors import InvalidId

from app.db import get_db
from app.deps import get_current_user, require_permissions
from app.utils import serialize_doc, to_object_id
from app.api.v1.notifications.routes import send_notification_to_user


router = APIRouter(prefix="/cash-advances", tags=["cash-advances"])


@router.patch("/{item_id}/approve", dependencies=[Depends(require_permissions("cash-advances:approve"))])
async def approve_cash_advance(
    item_id: str,
    payload: dict[str, Any] = Body(default={}),
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_db()
    try:
        oid = to_object_id(item_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Not found")
    update_payload: dict[str, Any] = {
        "status": "approved",
        "approvedBy": user["id"],
        "approvedDate": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    if isinstance(payload, dict) and payload.get("notes") is not None:
        update_payload["notes"] = payload["notes"]

    result = await db["cash_advances"].update_one(
        {"_id": oid}, {"$set": update_payload}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    doc = await db["cash_advances"].find_one({"_id": oid})

    # Notify the requester that their cash advance was approved
    requester_id = str(doc.get("requestedBy") or "")
    amount = doc.get("amount", 0)
    if requester_id:
        try:
            await send_notification_to_user(
                requester_id,
                "Cash Advance Approved",
                f"Your cash advance of \u20B1{amount:,.2f} has been approved.",
                {"type": "cash_advance_approved", "id": item_id},
            )
        except Exception:
            pass  # Non-critical — don't fail the request

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
    try:
        oid = to_object_id(item_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Not found")
    update_payload = {
        "status": "declined",
        "declineReason": decline_reason,
        "declinedDate": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    if isinstance(payload, dict) and payload.get("notes") is not None:
        update_payload["notes"] = payload["notes"]

    result = await db["cash_advances"].update_one(
        {"_id": oid}, {"$set": update_payload}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    doc = await db["cash_advances"].find_one({"_id": oid})

    # Notify the requester that their cash advance was declined
    requester_id = str(doc.get("requestedBy") or "")
    amount = doc.get("amount", 0)
    if requester_id:
        try:
            await send_notification_to_user(
                requester_id,
                "Cash Advance Declined",
                f"Your cash advance of \u20B1{amount:,.2f} was declined. Reason: {decline_reason}",
                {"type": "cash_advance_declined", "id": item_id},
            )
        except Exception:
            pass

    return serialize_doc(doc)
