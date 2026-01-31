from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from bson.errors import InvalidId

from app.db import get_db
from app.deps import require_permissions
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", dependencies=[Depends(require_permissions("companies:read"))])
async def list_companies(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
) -> dict[str, Any]:
    db = get_db()
    query: dict[str, Any] = {}
    if search:
        query["companyName"] = {"$regex": search, "$options": "i"}
    cursor = (
        db["companies"]
        .find(query)
        .sort("companyName", 1)
        .skip(offset)
        .limit(limit)
    )
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db["companies"].count_documents(query)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.post("", dependencies=[Depends(require_permissions("companies:create"))])
async def create_company(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    name = (payload.get("companyName") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="companyName is required")
    now = datetime.utcnow()
    db = get_db()
    existing = await db["companies"].find_one(
        {"companyName": {"$regex": f"^{name}$", "$options": "i"}}
    )
    if existing:
        await db["companies"].update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "companyName": name,
                    "companyAddress": payload.get("companyAddress"),
                    "companyPhone": payload.get("companyPhone"),
                    "companyTaxId": payload.get("companyTaxId"),
                    "updatedAt": now,
                }
            },
        )
        doc = await db["companies"].find_one({"_id": existing["_id"]})
        return serialize_doc(doc)

    doc = {
        "companyName": name,
        "companyAddress": payload.get("companyAddress"),
        "companyPhone": payload.get("companyPhone"),
        "companyTaxId": payload.get("companyTaxId"),
        "createdAt": now,
        "updatedAt": now,
    }
    result = await db["companies"].insert_one(doc)
    created = await db["companies"].find_one({"_id": result.inserted_id})
    return serialize_doc(created)


@router.patch("/{company_id}", dependencies=[Depends(require_permissions("companies:update"))])
async def update_company(
    company_id: str, payload: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    db = get_db()
    try:
        object_id = to_object_id(company_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Company not found")
    payload["updatedAt"] = datetime.utcnow()
    await db["companies"].update_one({"_id": object_id}, {"$set": payload})
    doc = await db["companies"].find_one({"_id": object_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Company not found")
    return serialize_doc(doc)


@router.delete(
    "/{company_id}", dependencies=[Depends(require_permissions("companies:delete"))]
)
async def delete_company(company_id: str) -> dict[str, Any]:
    db = get_db()
    try:
        object_id = to_object_id(company_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Company not found")
    result = await db["companies"].delete_one({"_id": object_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Company not found")
    return {"status": "deleted"}
