"""Transaction change-request endpoints.

Implements the spec's "Better Approach: REQUEST CHANGE" workflow:

    Gov clicks Flag on a transaction →
    System creates a change request →
    Broker is notified (via SSE / refetch) →
    Broker edits the underlying record →
    Gov verifies (resolves / rejects).

Scoping
-------
* **Government** users (regulators) can list every request and create new
  ones across companies. They are the only ones who can mark a request
  as ``resolved`` or ``rejected``.
* **Admin / broker / owner** users only see requests targeting their own
  company; they can move a request from ``open`` → ``in_progress``
  (acknowledging it) but not close it.

Document shape (collection ``transaction_change_requests``)::

    {
      _id, targetCollection, targetId, targetSummary,
      reason, status,                 # open | in_progress | resolved | rejected
      requestedBy, requestedByName,
      reviewedBy, reviewedByName, reviewedAt,
      companyId,                      # the company the target belongs to
      createdAt, updatedAt,
    }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.deps import get_current_user
from app.db import get_db
from app.infrastructure.roles.repository import RoleNames, get_role
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/change-requests", tags=["change-requests"])


_ALLOWED_TARGETS = {
    "trips",
    "catches",
    "fish_sales",
    "expenses",
    "cash_advances",
    "profit_shares",
    "vessels",
    "fish_training_samples",
}
_ALLOWED_STATUSES = {"open", "in_progress", "resolved", "rejected"}
_TRANSITIONS = {
    "open": {"in_progress", "rejected", "resolved"},
    "in_progress": {"resolved", "rejected", "open"},
    "resolved": set(),
    "rejected": {"open"},
}


async def _role_names(user: dict[str, Any]) -> list[str]:
    role_ids = user.get("roleIds") or []
    primary = user.get("roleId")
    if primary:
        role_ids = [primary, *role_ids]
    names: list[str] = []
    for rid in role_ids:
        if not rid:
            continue
        role = await get_role(str(rid))
        if role and role.get("name"):
            names.append(str(role["name"]).strip().lower())
    return names


async def _is_government(user: dict[str, Any]) -> bool:
    return RoleNames.GOVERNMENT in await _role_names(user)


async def _is_super(user: dict[str, Any]) -> bool:
    return RoleNames.SUPER in await _role_names(user)


def _company_oid(user: dict[str, Any]):
    cid = user.get("companyId")
    if not cid:
        return None
    try:
        return to_object_id(str(cid))
    except Exception:
        return cid


async def _resolve_target_company(target_collection: str, target_id: str):
    """Look up the target document so we can stamp the request with the
    company it belongs to (lets brokers/admins filter their queue)."""
    db = get_db()
    try:
        oid = to_object_id(target_id)
    except Exception:
        return None, None
    doc = await db[target_collection].find_one({"_id": oid})
    if not doc:
        return None, None
    summary_parts = [
        str(doc.get("name") or ""),
        str(doc.get("tripCode") or ""),
        str(doc.get("buyerName") or ""),
    ]
    summary = " ".join(p for p in summary_parts if p) or None
    return doc.get("companyId"), summary


@router.post("")
async def create_change_request(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    """Government regulator opens a request to flag a transaction for review."""
    if not await _is_government(user):
        raise HTTPException(
            status_code=403,
            detail="Only government users can flag transactions.",
        )
    target_collection = (payload.get("targetCollection") or "").strip()
    target_id = (payload.get("targetId") or "").strip()
    reason = (payload.get("reason") or "").strip()
    if target_collection not in _ALLOWED_TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"targetCollection must be one of: {sorted(_ALLOWED_TARGETS)}",
        )
    if not target_id:
        raise HTTPException(status_code=400, detail="targetId is required")
    if len(reason) < 5:
        raise HTTPException(
            status_code=400, detail="reason must be at least 5 characters"
        )

    company_id, target_summary = await _resolve_target_company(
        target_collection, target_id
    )

    db = get_db()
    now = datetime.now(timezone.utc)
    full_name = " ".join(
        p for p in [user.get("firstName"), user.get("lastName")] if p
    ).strip()
    doc = {
        "targetCollection": target_collection,
        "targetId": target_id,
        "targetSummary": target_summary or payload.get("targetSummary"),
        "reason": reason,
        "status": "open",
        "requestedBy": str(user.get("_id") or user.get("id") or ""),
        "requestedByName": full_name or user.get("email"),
        "companyId": company_id,
        "createdAt": now,
        "updatedAt": now,
    }
    result = await db["transaction_change_requests"].insert_one(doc)
    saved = await db["transaction_change_requests"].find_one(
        {"_id": result.inserted_id}
    )
    return serialize_doc(saved)


@router.get("")
async def list_change_requests(
    status: str | None = Query(None, pattern="^(open|in_progress|resolved|rejected)$"),
    target_collection: str | None = Query(None, alias="targetCollection"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_db()
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if target_collection:
        query["targetCollection"] = target_collection

    is_super = await _is_super(user)
    is_gov = await _is_government(user)
    if not is_super and not is_gov:
        # Brokers / admins / owners only see requests against their company.
        cid = _company_oid(user)
        if cid is None:
            return {"results": [], "total": 0, "limit": limit, "offset": offset}
        query["companyId"] = {"$in": [cid, str(cid)]}

    cursor = (
        db["transaction_change_requests"]
        .find(query)
        .sort("createdAt", -1)
        .skip(offset)
        .limit(limit)
    )
    results = [serialize_doc(d) async for d in cursor]
    total = await db["transaction_change_requests"].count_documents(query)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.post("/auto-flag-prices")
async def auto_flag_suspicious_prices(
    user: dict[str, Any] = Depends(get_current_user),
):
    """Government-triggered batch flagger.

    Computes the per-species mean ₱/kg across every fish-sale line item,
    then opens a change request for each line whose price deviates ≥50%
    from that mean. Skips fish-sale ids already covered by an open
    auto-flag so re-running the job is idempotent.
    """
    if not await _is_government(user):
        raise HTTPException(
            status_code=403,
            detail="Only government users can run the auto-flag job.",
        )

    db = get_db()
    sales = [s async for s in db["fish_sales"].find({})]

    # First pass — totals per species.
    totals: dict[str, dict[str, float]] = {}
    for s in sales:
        for line in s.get("lineItems") or []:
            name = (line or {}).get("speciesName")
            kg = float((line or {}).get("kilos") or 0)
            ppk = float((line or {}).get("pricePerKg") or 0)
            if not name or kg <= 0 or ppk <= 0:
                continue
            slot = totals.setdefault(name, {"kg": 0.0, "value": 0.0})
            slot["kg"] += kg
            slot["value"] += kg * ppk
    means = {
        name: (v["value"] / v["kg"]) for name, v in totals.items() if v["kg"] > 0
    }

    # Skip sales already covered by an open auto-flag.
    already_flagged: set[str] = set()
    async for cr in db["transaction_change_requests"].find(
        {
            "targetCollection": "fish_sales",
            "status": {"$in": ["open", "in_progress"]},
            "reason": {"$regex": "^Auto-flag:"},
        }
    ):
        if cr.get("targetId"):
            already_flagged.add(str(cr["targetId"]))

    full_name = " ".join(
        p for p in [user.get("firstName"), user.get("lastName")] if p
    ).strip()
    requester_name = full_name or user.get("email")
    user_id = str(user.get("_id") or user.get("id") or "")
    now = datetime.now(timezone.utc)

    created = 0
    for s in sales:
        sid = str(s.get("_id"))
        if sid in already_flagged:
            continue
        worst: tuple[str, float, float] | None = None  # (species, ppk, dev)
        for line in s.get("lineItems") or []:
            name = (line or {}).get("speciesName")
            ppk = float((line or {}).get("pricePerKg") or 0)
            mean = means.get(name)
            if not name or not mean or ppk <= 0:
                continue
            dev = abs(ppk - mean) / mean
            if dev >= 0.5 and (worst is None or dev > worst[2]):
                worst = (name, ppk, dev)
        if not worst:
            continue
        species, ppk, dev = worst
        mean = means[species]
        reason = (
            f"Auto-flag: {species} priced at ₱{ppk:,.2f}/kg "
            f"({(ppk/mean - 1) * 100:+.0f}% vs species mean of ₱{mean:,.2f})."
        )
        doc = {
            "targetCollection": "fish_sales",
            "targetId": sid,
            "targetSummary": s.get("buyerName"),
            "reason": reason,
            "status": "open",
            "requestedBy": user_id,
            "requestedByName": requester_name,
            "companyId": s.get("companyId"),
            "createdAt": now,
            "updatedAt": now,
        }
        await db["transaction_change_requests"].insert_one(doc)
        created += 1

    return {
        "scanned": len(sales),
        "created": created,
        "speciesTracked": len(means),
        "skippedAlreadyFlagged": len(already_flagged),
    }


@router.patch("/{req_id}/status")
async def update_status(
    req_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    new_status = (payload.get("status") or "").strip().lower()
    if new_status not in _ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="invalid status")

    db = get_db()
    try:
        oid = to_object_id(req_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Change request not found")

    doc = await db["transaction_change_requests"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Change request not found")

    current = (doc.get("status") or "open").strip().lower()
    if new_status not in _TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=400,
            detail=f"cannot transition from '{current}' to '{new_status}'",
        )

    is_gov = await _is_government(user)
    is_super = await _is_super(user)
    # Closing transitions (resolved / rejected) are gov-only. Brokers may
    # only acknowledge (open → in_progress) and mark themselves working on it.
    if new_status in {"resolved", "rejected"} and not (is_gov or is_super):
        raise HTTPException(
            status_code=403,
            detail="Only government users can resolve or reject a change request.",
        )
    # Brokers/admins can only touch their own company's requests.
    if not (is_gov or is_super):
        target_company = doc.get("companyId")
        user_company = _company_oid(user)
        if user_company is None or str(target_company) != str(user_company):
            raise HTTPException(status_code=403, detail="Forbidden")

    full_name = " ".join(
        p for p in [user.get("firstName"), user.get("lastName")] if p
    ).strip()
    update_fields: dict[str, Any] = {
        "status": new_status,
        "updatedAt": datetime.now(timezone.utc),
        "reviewedBy": str(user.get("_id") or user.get("id") or ""),
        "reviewedByName": full_name or user.get("email"),
        "reviewedAt": datetime.now(timezone.utc),
    }
    if payload.get("note"):
        update_fields["resolutionNote"] = str(payload["note"]).strip()

    await db["transaction_change_requests"].update_one(
        {"_id": oid}, {"$set": update_fields}
    )
    updated = await db["transaction_change_requests"].find_one({"_id": oid})
    return serialize_doc(updated)
