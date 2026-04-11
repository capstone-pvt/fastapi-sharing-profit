"""Custom profit-sharing endpoints.

Supplements the generic CRUD router (which handles basic create/read on
``/profit-shares``) with computation-specific routes:

* ``POST /profit-shares/compute``  — preview only (no persistence)
* ``POST /profit-shares/generate`` — compute + save to ``profit_shares``
* ``PATCH /profit-shares/{id}/status`` — status transitions
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.db import get_db
from app.deps import get_current_user, require_permissions
from app.domain.profit_shares.services import compute_profit_share
from app.utils import serialize_doc, to_object_id
from app.api.v1.notifications.routes import send_notification_to_user, send_notification_to_company_role

router = APIRouter(prefix="/profit-shares", tags=["profit-shares"])

VALID_STATUS_TRANSITIONS = {
    "draft": {"finalized"},
    "finalized": {"paid", "draft"},  # allow reverting to draft
    "paid": set(),                    # terminal state
}


@router.post(
    "/compute",
    dependencies=[Depends(require_permissions("profit-shares:generate"))],
)
async def compute(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Preview profit share computation for a trip (no persistence)."""
    trip_id = payload.get("tripId")
    if not trip_id:
        raise HTTPException(status_code=400, detail="tripId is required")

    policy_id = payload.get("policyId")
    company_id = str(user.get("companyId") or "")

    try:
        result = await compute_profit_share(
            trip_id=str(trip_id),
            policy_id=policy_id,
            company_id=company_id or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Computation error: {exc}")

    return result


@router.post(
    "/generate",
    dependencies=[Depends(require_permissions("profit-shares:generate"))],
)
async def generate(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Compute AND persist a profit share for a trip."""
    trip_id = payload.get("tripId")
    if not trip_id:
        raise HTTPException(status_code=400, detail="tripId is required")

    policy_id = payload.get("policyId")
    status = payload.get("status", "draft")
    company_id = str(user.get("companyId") or "")
    notes = payload.get("notes")

    try:
        result = await compute_profit_share(
            trip_id=str(trip_id),
            policy_id=policy_id,
            company_id=company_id or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Computation error: {exc}")

    db = get_db()
    now = datetime.now(timezone.utc)

    user_id = str(user.get("_id") or user.get("id") or "")

    doc = {
        **result,
        "generatedBy": user_id,
        "calculationDate": now,
        "status": status,
        "notes": notes,
        "createdAt": now,
        "updatedAt": now,
    }

    # Attach companyId for multi-tenant scoping
    raw_company = user.get("companyId")
    if raw_company:
        doc["companyId"] = (
            to_object_id(str(raw_company))
            if not hasattr(raw_company, "__class__")
            or raw_company.__class__.__name__ != "ObjectId"
            else raw_company
        )
        doc["companyName"] = user.get("companyName")

    insert_result = await db["profit_shares"].insert_one(doc)
    saved = await db["profit_shares"].find_one({"_id": insert_result.inserted_id})

    # Notify crew members that a profit share was generated for their trip
    crew_breakdown = result.get("crewBreakdown") or []
    gross_revenue = result.get("grossRevenue", 0)
    for crew in crew_breakdown:
        crew_id = crew.get("crewId", "")
        net_payout = crew.get("netPayout", 0)
        if crew_id:
            try:
                await send_notification_to_user(
                    crew_id,
                    "Profit Share Generated",
                    f"A profit share of \u20B1{net_payout:,.2f} has been computed for your trip. Review your earnings.",
                    {"type": "profit_share_generated", "id": str(insert_result.inserted_id)},
                )
            except Exception:
                pass

    # Notify brokers in the company
    company_id = user.get("companyId")
    if company_id:
        try:
            await send_notification_to_company_role(
                company_id,
                "broker",
                "Profit Share Generated",
                f"A profit share (gross \u20B1{gross_revenue:,.2f}) was generated. Review the distribution.",
                {"type": "profit_share_generated", "id": str(insert_result.inserted_id)},
                exclude_user_id=user_id,
            )
        except Exception:
            pass

    return serialize_doc(saved)


@router.patch(
    "/{item_id}/status",
    dependencies=[Depends(require_permissions("profit-shares:generate"))],
)
async def update_status(
    item_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Transition a profit share's status (draft → finalized → paid)."""
    new_status = (payload.get("status") or "").strip().lower()
    if not new_status:
        raise HTTPException(status_code=400, detail="status is required")

    db = get_db()
    try:
        oid = to_object_id(item_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Invalid ID")

    doc = await db["profit_shares"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Profit share not found")

    current_status = (doc.get("status") or "draft").strip().lower()
    allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{current_status}' to '{new_status}'. "
            f"Allowed: {allowed or 'none (terminal state)'}",
        )

    now = datetime.now(timezone.utc)
    update_fields: dict[str, Any] = {
        "status": new_status,
        "updatedAt": now,
    }

    # Audit: record who made the transition
    user_id = str(user.get("_id") or user.get("id") or "")
    if new_status == "finalized":
        update_fields["finalizedBy"] = user_id
        update_fields["finalizedAt"] = now
    elif new_status == "paid":
        update_fields["paidBy"] = user_id
        update_fields["paidAt"] = now

    await db["profit_shares"].update_one({"_id": oid}, {"$set": update_fields})
    updated = await db["profit_shares"].find_one({"_id": oid})
    return serialize_doc(updated)
