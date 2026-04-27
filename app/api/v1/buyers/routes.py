"""
Buyers + per-buyer running balance.

Brokers can record fish sales on credit (per-entry `paymentType: 'credit'`);
those credit lines accumulate as the buyer's outstanding balance. Cash
collection or settlement adjusts the balance back down.

Endpoints:
- GET  /buyers                       — list buyers in scope
- POST /buyers                       — create
- GET  /buyers/{id}                  — single
- PATCH /buyers/{id}                 — update name/contact
- POST /buyers/{id}/balance          — adjust balance ({amount, reason})
- GET  /buyers/{id}/ledger           — recent balance entries
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.db import get_db
from app.deps import get_current_user
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/buyers", tags=["buyers"])


def _user_id(user: dict[str, Any]) -> str:
    return str(user.get("id") or user.get("_id"))


@router.get("")
async def list_buyers(
    user: dict[str, Any] = Depends(get_current_user),
    limit: int = Query(200, ge=1, le=500),
):
    db = get_db()
    company_id = user.get("companyId")
    query: dict[str, Any] = {}
    if company_id:
        cid = str(company_id)
        candidates: list[Any] = [cid]
        try:
            candidates.append(to_object_id(cid))
        except Exception:
            pass
        query["companyId"] = {"$in": candidates}
    cursor = db["buyers"].find(query).sort("name", 1).limit(limit)
    results = [serialize_doc(d) async for d in cursor]
    return {"results": results, "total": len(results)}


@router.post("")
async def create_buyer(
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "name": name,
        "contactNumber": payload.get("contactNumber"),
        "notes": payload.get("notes"),
        "companyId": str(user.get("companyId") or "") or None,
        "createdBy": _user_id(user),
        "balance": 0.0,
        "createdAt": now,
        "updatedAt": now,
    }
    res = await db["buyers"].insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize_doc(doc)


@router.get("/{buyer_id}")
async def get_buyer(
    buyer_id: str,
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_db()
    try:
        oid = to_object_id(buyer_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid buyer_id")
    doc = await db["buyers"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Buyer not found")
    return serialize_doc(doc)


@router.patch("/{buyer_id}")
async def update_buyer(
    buyer_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_db()
    try:
        oid = to_object_id(buyer_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid buyer_id")
    update = {
        k: payload[k]
        for k in ("name", "contactNumber", "notes")
        if k in payload
    }
    if not update:
        raise HTTPException(status_code=400, detail="No editable fields")
    update["updatedAt"] = datetime.now(timezone.utc)
    await db["buyers"].update_one({"_id": oid}, {"$set": update})
    doc = await db["buyers"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Buyer not found")
    return serialize_doc(doc)


@router.post("/{buyer_id}/balance")
async def adjust_balance(
    buyer_id: str,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    """Add or subtract from a buyer's balance. Positive amounts increase
    credit owed (use for credit sales); negative amounts settle it (use for
    cash collection)."""
    try:
        amount = float(payload.get("amount"))
    except Exception:
        raise HTTPException(status_code=400, detail="amount must be a number")
    if amount == 0:
        raise HTTPException(status_code=400, detail="amount cannot be zero")
    reason = (payload.get("reason") or "").strip() or None
    fish_sale_id = payload.get("fishSaleId")

    db = get_db()
    try:
        oid = to_object_id(buyer_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid buyer_id")
    buyer = await db["buyers"].find_one({"_id": oid})
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")

    now = datetime.now(timezone.utc)
    new_balance = float(buyer.get("balance") or 0) + amount
    await db["buyers"].update_one(
        {"_id": oid},
        {"$set": {"balance": new_balance, "updatedAt": now}},
    )
    await db["buyer_balance_ledger"].insert_one(
        {
            "buyerId": str(oid),
            "amount": amount,
            "balanceAfter": new_balance,
            "reason": reason,
            "fishSaleId": fish_sale_id,
            "createdBy": _user_id(user),
            "createdAt": now,
        }
    )
    return {
        "buyerId": str(oid),
        "balance": new_balance,
        "delta": amount,
        "reason": reason,
    }


@router.get("/{buyer_id}/ledger")
async def buyer_ledger(
    buyer_id: str,
    limit: int = Query(50, ge=1, le=200),
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_db()
    cursor = (
        db["buyer_balance_ledger"]
        .find({"buyerId": buyer_id})
        .sort("createdAt", -1)
        .limit(limit)
    )
    results = [serialize_doc(d) async for d in cursor]
    return {"results": results, "total": len(results)}
