from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("", dependencies=[Depends(get_current_user)])
async def list_permissions():
    db = get_db()
    results = [serialize_doc(doc) async for doc in db["permissions"].find({})]
    return results


@router.get("/{perm_id}", dependencies=[Depends(get_current_user)])
async def get_permission(perm_id: str):
    db = get_db()
    doc = await db["permissions"].find_one({"_id": to_object_id(perm_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Permission not found")
    return serialize_doc(doc)


@router.post("", dependencies=[Depends(require_roles("admin"))])
async def create_permission(payload: dict[str, Any] = Body(...)):
    db = get_db()
    payload["createdAt"] = datetime.utcnow()
    payload["updatedAt"] = datetime.utcnow()
    result = await db["permissions"].insert_one(payload)
    doc = await db["permissions"].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


@router.patch("/{perm_id}", dependencies=[Depends(require_roles("admin"))])
async def update_permission(perm_id: str, payload: dict[str, Any] = Body(...)):
    db = get_db()
    payload["updatedAt"] = datetime.utcnow()
    await db["permissions"].update_one({"_id": to_object_id(perm_id)}, {"$set": payload})
    doc = await db["permissions"].find_one({"_id": to_object_id(perm_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Permission not found")
    return serialize_doc(doc)


@router.delete("/{perm_id}", dependencies=[Depends(require_roles("admin"))])
async def delete_permission(perm_id: str):
    db = get_db()
    result = await db["permissions"].delete_one({"_id": to_object_id(perm_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Permission not found")
    return {"status": "deleted"}
