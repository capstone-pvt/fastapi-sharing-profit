from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from app.core.security import hash_password
from app.db import get_db
from app.deps import require_permissions
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", dependencies=[Depends(require_permissions("user:read"))])
async def list_users(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    query: dict[str, Any] = {}
    search = request.query_params.get("search")
    if search:
        query["email"] = {"$regex": search, "$options": "i"}
    cursor = db["users"].find(query).skip(offset).limit(limit)
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db["users"].count_documents(query)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/{user_id}", dependencies=[Depends(require_permissions("user:read"))])
async def get_user(user_id: str):
    db = get_db()
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_doc(doc)


@router.post("", dependencies=[Depends(require_permissions("user:create"))])
async def create_user(payload: dict[str, Any] = Body(...)):
    db = get_db()
    required = ["email", "password", "firstName", "lastName", "roleId"]
    if any(not payload.get(field) for field in required):
        raise HTTPException(status_code=400, detail="Missing required fields")
    payload["password"] = hash_password(payload["password"])
    payload["role"] = to_object_id(payload.pop("roleId"))
    payload["createdAt"] = datetime.utcnow()
    payload["updatedAt"] = datetime.utcnow()
    result = await db["users"].insert_one(payload)
    doc = await db["users"].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


@router.patch("/{user_id}", dependencies=[Depends(require_permissions("user:update"))])
async def update_user(user_id: str, payload: dict[str, Any] = Body(...)):
    db = get_db()
    if "password" in payload:
        payload["password"] = hash_password(payload["password"])
    if "roleId" in payload:
        payload["role"] = to_object_id(payload.pop("roleId"))
    payload["updatedAt"] = datetime.utcnow()
    await db["users"].update_one({"_id": to_object_id(user_id)}, {"$set": payload})
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_doc(doc)


@router.delete("/{user_id}", dependencies=[Depends(require_permissions("user:delete"))])
async def delete_user(user_id: str):
    db = get_db()
    result = await db["users"].delete_one({"_id": to_object_id(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted"}
