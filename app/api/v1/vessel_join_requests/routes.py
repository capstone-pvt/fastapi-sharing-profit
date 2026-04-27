"""
Crew vessel-join requests.

A crew user (mobile-only) browses available vessels and submits a join
request. The vessel owner (web/mobile) sees pending requests for their
vessels and approves or rejects them. On approval, the crew is added to
the `crew` collection scoped to that vessel.

This is distinct from `role_requests` (which upgrades a user's *role* to
broker/owner). Here the user is already crew; they're picking which
vessel they want to fish on.
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.api.v1.notifications.routes import send_notification_to_user
from app.db import get_db
from app.deps import get_current_user
from app.role_utils import get_user_role_names
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/vessel-join-requests", tags=["vessel-join-requests"])


def _user_id_str(user: dict[str, Any]) -> str:
    return str(user.get("id") or user.get("_id"))


async def _is_owner_of(user: dict[str, Any], vessel_doc: dict[str, Any]) -> bool:
    user_id = _user_id_str(user)
    return str(vessel_doc.get("vesselOwnerId") or "") == user_id or str(
        vessel_doc.get("ownerId") or ""
    ) == user_id


async def _resolve_owner_user_id(db, vessel: dict[str, Any]) -> str | None:
    """A vessel's `vesselOwnerId` points at the `vessel_owners` collection,
    not directly at the user. Walk that link so we can match the requesting
    owner's user.id when filtering pending requests."""
    direct = vessel.get("ownerId")
    if direct:
        return str(direct)
    vo_id = vessel.get("vesselOwnerId")
    if not vo_id:
        return None
    candidates: list[Any] = [str(vo_id)]
    try:
        candidates.append(to_object_id(str(vo_id)))
    except Exception:
        pass
    vo = await db["vessel_owners"].find_one({"_id": {"$in": candidates}})
    if vo:
        return str(vo.get("userId") or "")
    return str(vo_id)


@router.get("/available-vessels")
async def list_available_vessels(
    user: dict[str, Any] = Depends(get_current_user),
):
    """Crew browse: vessels open for join requests in the user's company.

    Vessels store `companyId` as either an ObjectId or a stringified hex,
    depending on which seeder/route created them — match both forms so the
    crew browse page always sees the user's fleet.
    """
    db = get_db()
    company_id = user.get("companyId")
    query: dict[str, Any] = {}
    if company_id:
        cid_str = str(company_id)
        candidates: list[Any] = [cid_str]
        try:
            candidates.append(to_object_id(cid_str))
        except Exception:
            pass
        query["companyId"] = {"$in": candidates}
    cursor = db["vessels"].find(query).sort("name", 1)
    results = [serialize_doc(doc) async for doc in cursor]
    return {"results": results, "total": len(results)}


@router.post("")
async def create_join_request(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    vessel_id = (payload.get("vesselId") or "").strip()
    if not vessel_id:
        raise HTTPException(status_code=400, detail="vesselId is required")
    note = (payload.get("note") or "").strip() or None

    db = get_db()
    try:
        vessel_oid = to_object_id(vessel_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vesselId")
    vessel = await db["vessels"].find_one({"_id": vessel_oid})
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")

    user_id = _user_id_str(user)
    existing = await db["vessel_join_requests"].find_one(
        {"userId": user_id, "vesselId": vessel_id, "status": "pending"}
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="You already have a pending request for this vessel"
        )

    # Resolve the owner's *user id* (not the vessel_owners doc id) so the
    # owner-facing endpoint can match `vesselOwnerId == current user`.
    owner_user_id = await _resolve_owner_user_id(db, vessel)

    now = datetime.now(timezone.utc)
    doc = {
        "userId": user_id,
        "userName": f"{user.get('firstName','')} {user.get('lastName','')}".strip(),
        "userEmail": user.get("email", ""),
        "vesselId": vessel_id,
        "vesselName": vessel.get("name") or "",
        "vesselOwnerId": owner_user_id or "",
        "companyId": str(user.get("companyId") or vessel.get("companyId") or "") or None,
        "note": note,
        "status": "pending",
        "reviewedBy": None,
        "reviewedAt": None,
        "createdAt": now,
        "updatedAt": now,
    }
    result = await db["vessel_join_requests"].insert_one(doc)
    doc["_id"] = result.inserted_id

    if owner_user_id:
        try:
            await send_notification_to_user(
                owner_user_id,
                title="New crew join request",
                body=f"{doc['userName'] or doc['userEmail']} wants to join {doc['vesselName']}",
                category="crew_request",
                data={"requestId": str(result.inserted_id), "vesselId": vessel_id},
            )
        except Exception:
            pass  # notifications are best-effort

    return serialize_doc(doc)


@router.get("/my")
async def my_join_requests(
    user: dict[str, Any] = Depends(get_current_user),
):
    """Crew view: my own join requests with status."""
    db = get_db()
    cursor = (
        db["vessel_join_requests"]
        .find({"userId": _user_id_str(user)})
        .sort("createdAt", -1)
    )
    results = [serialize_doc(doc) async for doc in cursor]
    return {"results": results, "total": len(results)}


@router.get("")
async def list_requests_for_owner(
    status: str = Query("pending"),
    vessel_id: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
):
    """Vessel owner view: requests against vessels they own.

    Admins / supers see all requests in their company so they can monitor
    the queue from the operations sidebar.
    """
    db = get_db()
    query: dict[str, Any] = {"status": status}
    role_names = await get_user_role_names(user)
    is_super = "super" in role_names
    is_admin = "admin" in role_names
    if is_super:
        pass  # see everything
    elif is_admin:
        company_id = user.get("companyId")
        if company_id:
            query["companyId"] = str(company_id)
        else:
            return {"results": [], "total": 0}
    else:
        query["vesselOwnerId"] = _user_id_str(user)
    if vessel_id:
        query["vesselId"] = vessel_id
    cursor = db["vessel_join_requests"].find(query).sort("createdAt", -1)
    results = [serialize_doc(doc) async for doc in cursor]
    return {"results": results, "total": len(results)}


@router.patch("/{request_id}")
async def review_request(
    request_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    """Vessel owner approves or rejects. On approve, also accepts an optional
    `crewType` (pakura | tongko) which gets recorded on the new crew row."""
    new_status = (payload.get("status") or "").strip().lower()
    if new_status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be approved|rejected")

    db = get_db()
    try:
        req_oid = to_object_id(request_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request_id")
    req = await db["vessel_join_requests"].find_one({"_id": req_oid})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.get("status") != "pending":
        raise HTTPException(
            status_code=409, detail=f"Request already {req.get('status')}"
        )

    role_names = await get_user_role_names(user)
    is_super = "super" in role_names
    if not is_super and req.get("vesselOwnerId") != _user_id_str(user):
        raise HTTPException(status_code=403, detail="Forbidden")

    now = datetime.now(timezone.utc)
    update_fields = {
        "status": new_status,
        "reviewedBy": _user_id_str(user),
        "reviewedAt": now,
        "updatedAt": now,
    }

    if new_status == "approved":
        crew_type = (payload.get("crewType") or "pakura").strip().lower()
        if crew_type not in ("pakura", "tongko"):
            raise HTTPException(status_code=400, detail="crewType must be pakura|tongko")
        # Idempotent: only insert if not already on the vessel.
        existing_crew = await db["crew"].find_one(
            {"userId": req["userId"], "vesselId": req["vesselId"]}
        )
        if not existing_crew:
            await db["crew"].insert_one(
                {
                    "userId": req["userId"],
                    "userName": req.get("userName"),
                    "vesselId": req["vesselId"],
                    "crewType": crew_type,
                    "status": "active",
                    "companyId": req.get("companyId"),
                    "createdAt": now,
                    "updatedAt": now,
                }
            )

    await db["vessel_join_requests"].update_one(
        {"_id": req_oid}, {"$set": update_fields}
    )
    updated = await db["vessel_join_requests"].find_one({"_id": req_oid})

    requester_id = req.get("userId")
    if requester_id:
        try:
            verb = "approved" if new_status == "approved" else "rejected"
            await send_notification_to_user(
                str(requester_id),
                title=f"Vessel join request {verb}",
                body=f"Your request to join {req.get('vesselName') or 'vessel'} was {verb}.",
                category="crew_request",
                data={
                    "requestId": str(req_oid),
                    "vesselId": str(req.get("vesselId") or ""),
                    "status": new_status,
                },
            )
        except Exception:
            pass

    return serialize_doc(updated)


@router.post("/crew/{crew_id}/confirm-captain")
async def confirm_boat_captain(
    crew_id: str,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Boat Captain confirms their assignment (sets a flag on the crew row)."""
    db = get_db()
    try:
        crew_oid = to_object_id(crew_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid crew_id")
    crew = await db["crew"].find_one({"_id": crew_oid})
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")
    if str(crew.get("userId")) != _user_id_str(user):
        raise HTTPException(status_code=403, detail="Forbidden")

    now = datetime.now(timezone.utc)
    await db["crew"].update_one(
        {"_id": crew_oid},
        {
            "$set": {
                "boatCaptainConfirmedAt": now,
                "isBoatCaptain": True,
                "updatedAt": now,
            }
        },
    )
    return serialize_doc(await db["crew"].find_one({"_id": crew_oid}))


@router.post("/crew/{crew_id}/assign-captain")
async def assign_boat_captain(
    crew_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    user: dict[str, Any] = Depends(get_current_user),
):
    """Vessel owner promotes a crew member to boat captain.

    Sets `isBoatCaptain=True` and `assignedCaptainAt`; clears any existing
    confirmation so the captain has to confirm again. Notifies the captain.
    Caller must be the vessel's owner (resolved via vessel_owners.userId)
    or an admin/super.
    """
    db = get_db()
    try:
        crew_oid = to_object_id(crew_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid crew_id")
    crew = await db["crew"].find_one({"_id": crew_oid})
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")

    role_names = await get_user_role_names(user)
    is_super = "super" in role_names
    is_admin = "admin" in role_names
    if not (is_super or is_admin):
        vessel_id = crew.get("vesselId")
        if not vessel_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            v_oid = to_object_id(str(vessel_id))
            vessel = await db["vessels"].find_one({"_id": v_oid})
        except Exception:
            vessel = None
        if not vessel:
            raise HTTPException(status_code=404, detail="Vessel not found")
        owner_user_id = await _resolve_owner_user_id(db, vessel)
        if owner_user_id != _user_id_str(user):
            raise HTTPException(status_code=403, detail="Forbidden")

    revoke = bool(payload.get("revoke"))
    now = datetime.now(timezone.utc)
    update: dict[str, Any] = {"updatedAt": now}
    if revoke:
        update.update(
            {
                "isBoatCaptain": False,
                "assignedCaptainAt": None,
                "boatCaptainConfirmedAt": None,
            }
        )
    else:
        update.update(
            {
                "isBoatCaptain": True,
                "assignedCaptainAt": now,
                "boatCaptainConfirmedAt": None,
            }
        )

    await db["crew"].update_one({"_id": crew_oid}, {"$set": update})
    updated = await db["crew"].find_one({"_id": crew_oid})

    target_user_id = crew.get("userId")
    if target_user_id and not revoke:
        try:
            await send_notification_to_user(
                str(target_user_id),
                title="You've been assigned as Boat Captain",
                body="Open the Boat Captain dashboard to confirm.",
                category="boat_captain",
                data={"crewId": str(crew_oid)},
            )
        except Exception:
            pass

    return serialize_doc(updated)
