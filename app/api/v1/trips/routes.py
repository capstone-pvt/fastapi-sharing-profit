"""Trips router – Hybrid Model.

Rules:
  - A trip is ALWAYS owned by the Vessel Owner (``ownerId``).
  - A Broker can be assigned as **financer** and/or **encoder** on the trip.

The ``ownerId`` field is resolved from the vessel linked to the trip.
When a Broker creates a trip they must specify a ``vesselId``; the API
looks up the vessel's owner and records that as ``ownerId`` while
auto-assigning the broker as ``financerId`` and ``encoderId``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from app.db import get_db
from app.deps import get_current_user, require_permissions
from app.infrastructure.roles.repository import RoleNames, get_role
from app.utils import serialize_doc, to_object_id

router = APIRouter(prefix="/trips", tags=["trips"])

COLLECTION = "trips"

_FILTER_FIELDS = frozenset({"status", "tripId", "boatId", "vesselId", "ownerId"})

# Maps an incoming singular query param to the plural array field stored on
# the trip document. Membership against the array is matched by supplying
# the scalar value (Mongo treats it as "any element equals").
_ARRAY_FIELD_FILTERS: dict[str, str] = {"crewId": "crewIds"}


# ── helpers ──────────────────────────────────────────────────────────


def _build_query_from_params(params: Mapping[str, str]) -> dict[str, Any]:
    query: dict[str, Any] = {}
    for key, value in params.items():
        if key in {"limit", "offset"}:
            continue
        array_field = _ARRAY_FIELD_FILTERS.get(key)
        if array_field is not None:
            query[array_field] = value
            continue
        if key in _FILTER_FIELDS:
            query[key] = value
    return query


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


async def _is_super_user(user: dict[str, Any]) -> bool:
    return (await _get_role_name(user)).strip().lower() == RoleNames.SUPER


async def _is_role(user: dict[str, Any], role: str) -> bool:
    return (await _get_role_name(user)).strip().lower() == role


def _company_id_value(data: dict[str, Any]) -> str | None:
    cid = data.get("companyId")
    return str(cid) if cid else None


def _company_object_id(company_id: str | None):
    if not company_id:
        return None
    try:
        return to_object_id(company_id)
    except Exception:
        return None


async def _resolve_vessel_owner(vessel_id: str) -> str | None:
    """Return the ownerId string from the vessel_owners collection
    that is linked to the given vessel, or from the vessel document
    itself if it carries an ``ownerId`` field."""
    db = get_db()
    vessel = await db["vessels"].find_one({"_id": to_object_id(vessel_id)})
    if not vessel:
        return None
    # Try direct ownerId on the vessel document first
    owner_id = vessel.get("ownerId")
    if owner_id:
        return str(owner_id)
    # Fallback: look in vessel_owners collection
    owner_doc = await db["vessel_owners"].find_one({"vesselId": to_object_id(vessel_id)})
    if owner_doc:
        return str(owner_doc.get("userId") or owner_doc["_id"])
    return None


# ── LIST ─────────────────────────────────────────────────────────────

@router.get("", dependencies=[Depends(require_permissions("trips:read"))])
async def list_trips(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_db()
    query = _build_query_from_params(request.query_params)
    if not await _is_super_user(user):
        company_id = _company_id_value(user)
        object_id = _company_object_id(company_id)
        if not object_id:
            return {"results": [], "total": 0, "limit": limit, "offset": offset}
        query["companyId"] = {"$in": [object_id, str(object_id)]}
    cursor = (
        db[COLLECTION].find(query).sort("createdAt", -1).skip(offset).limit(limit)
    )
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db[COLLECTION].count_documents(query)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


# ── GET ──────────────────────────────────────────────────────────────

@router.get("/{item_id}", dependencies=[Depends(require_permissions("trips:read"))])
async def get_trip(
    item_id: str,
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_db()
    doc = await db[COLLECTION].find_one({"_id": to_object_id(item_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if not await _is_super_user(user):
        company_id = _company_id_value(user)
        target_company_id = _company_id_value(doc)
        if not company_id or company_id != target_company_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    return serialize_doc(doc)


# ── CREATE ───────────────────────────────────────────────────────────

@router.post("", dependencies=[Depends(require_permissions("trips:create"))])
async def create_trip(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_db()
    payload.pop("_id", None)
    payload.pop("id", None)
    now = datetime.now(timezone.utc)
    payload["createdAt"] = now
    payload["updatedAt"] = now

    is_super = await _is_super_user(user)
    user_id = str(user.get("_id") or user.get("id") or "")

    # ── company scoping (same as generic CRUD) ──
    if not is_super:
        company_id = _company_id_value(user)
        object_id = _company_object_id(company_id)
        if not object_id:
            raise HTTPException(status_code=403, detail="Company not set")
        payload["companyId"] = object_id
    elif payload.get("companyId"):
        object_id = _company_object_id(str(payload["companyId"]))
        if not object_id:
            raise HTTPException(status_code=400, detail="Invalid companyId")
        payload["companyId"] = object_id
    company_name = user.get("companyName")
    if company_name and not is_super:
        payload["companyName"] = company_name

    # ── Hybrid Model: resolve owner from vessel ──
    vessel_id = payload.get("vesselId") or payload.get("vessel_id")
    if vessel_id:
        owner_id = await _resolve_vessel_owner(str(vessel_id))
        if owner_id:
            payload["ownerId"] = owner_id
        else:
            # Vessel exists but has no linked owner – fall back to current user
            payload.setdefault("ownerId", user_id)
    else:
        # No vessel specified – owner is the current user
        payload.setdefault("ownerId", user_id)

    # ── Broker auto-assignment as financer + encoder ──
    if await _is_role(user, RoleNames.BROKER):
        payload.setdefault("financerId", user_id)
        payload.setdefault("encoderId", user_id)

    result = await db[COLLECTION].insert_one(payload)
    doc = await db[COLLECTION].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


# ── UPDATE ───────────────────────────────────────────────────────────

@router.patch("/{item_id}", dependencies=[Depends(require_permissions("trips:update"))])
async def update_trip(
    item_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_db()
    payload.pop("_id", None)
    payload.pop("id", None)
    payload.pop("createdAt", None)
    payload.pop("companyName", None)
    # ownerId is immutable – trip always belongs to the vessel owner
    payload.pop("ownerId", None)

    is_super = await _is_super_user(user)
    if not is_super:
        payload.pop("companyId", None)
    elif payload.get("companyId"):
        object_id = _company_object_id(str(payload["companyId"]))
        if not object_id:
            raise HTTPException(status_code=400, detail="Invalid companyId")
        payload["companyId"] = object_id
    payload["updatedAt"] = datetime.now(timezone.utc)

    doc = await db[COLLECTION].find_one({"_id": to_object_id(item_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    if not is_super:
        company_id = _company_id_value(user)
        target_company_id = _company_id_value(doc)
        if not company_id or company_id != target_company_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    await db[COLLECTION].update_one(
        {"_id": to_object_id(item_id)}, {"$set": payload}
    )
    doc = await db[COLLECTION].find_one({"_id": to_object_id(item_id)})
    return serialize_doc(doc)


# ── DELETE ───────────────────────────────────────────────────────────

@router.delete("/{item_id}", dependencies=[Depends(require_permissions("trips:delete"))])
async def delete_trip(
    item_id: str,
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_db()
    if not await _is_super_user(user):
        doc = await db[COLLECTION].find_one({"_id": to_object_id(item_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Not found")
        company_id = _company_id_value(user)
        target_company_id = _company_id_value(doc)
        if not company_id or company_id != target_company_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    result = await db[COLLECTION].delete_one({"_id": to_object_id(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "deleted"}


@router.patch(
    "/{item_id}/approve-sales",
    dependencies=[Depends(require_permissions("trips:update"))],
)
async def approve_trip_sales(
    item_id: str,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Mark fish sales for a trip as reviewed and approved.

    This is required before profit share computation can be triggered.
    Only the Boat Owner (or Admin) should approve sales recorded by the Broker.
    """
    db = get_db()
    doc = await db[COLLECTION].find_one({"_id": to_object_id(item_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Trip not found")

    full_name = " ".join(
        part for part in [user.get("firstName"), user.get("lastName")] if part
    ).strip()
    approved_by = full_name if full_name else user.get("email")

    now = datetime.now(timezone.utc)
    await db[COLLECTION].update_one(
        {"_id": to_object_id(item_id)},
        {
            "$set": {
                "salesApproved": True,
                "salesApprovedBy": approved_by,
                "salesApprovedAt": now,
                "updatedAt": now,
            }
        },
    )
    updated = await db[COLLECTION].find_one({"_id": to_object_id(item_id)})
    return serialize_doc(updated)
