from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", dependencies=[Depends(get_current_user)])
async def list_roles():
    db = get_db()
    results = [serialize_doc(doc) async for doc in db["roles"].find({})]
    return results


@router.get("/{role_id}", dependencies=[Depends(get_current_user)])
async def get_role(role_id: str):
    db = get_db()
    doc = await db["roles"].find_one({"_id": to_object_id(role_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    return serialize_doc(doc)


@router.post("", dependencies=[Depends(require_roles("admin"))])
async def create_role(payload: dict[str, Any] = Body(...)):
    db = get_db()
    payload["permissions"] = payload.get("permissions", [])
    payload["createdAt"] = datetime.utcnow()
    payload["updatedAt"] = datetime.utcnow()
    result = await db["roles"].insert_one(payload)
    doc = await db["roles"].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


@router.patch("/{role_id}", dependencies=[Depends(require_roles("admin"))])
async def update_role(role_id: str, payload: dict[str, Any] = Body(...)):
    db = get_db()
    payload["updatedAt"] = datetime.utcnow()
    await db["roles"].update_one({"_id": to_object_id(role_id)}, {"$set": payload})
    doc = await db["roles"].find_one({"_id": to_object_id(role_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    return serialize_doc(doc)


@router.post("/{role_id}/permissions", dependencies=[Depends(require_roles("admin"))])
async def add_permissions(role_id: str, payload: dict[str, Any] = Body(...)):
    db = get_db()
    permissions = payload.get("permissions", [])
    await db["roles"].update_one(
        {"_id": to_object_id(role_id)},
        {"$addToSet": {"permissions": {"$each": permissions}}},
    )
    doc = await db["roles"].find_one({"_id": to_object_id(role_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    return serialize_doc(doc)


@router.delete("/{role_id}/permissions", dependencies=[Depends(require_roles("admin"))])
async def remove_permissions(role_id: str, payload: dict[str, Any] = Body(...)):
    db = get_db()
    permissions = payload.get("permissions", [])
    await db["roles"].update_one(
        {"_id": to_object_id(role_id)}, {"$pull": {"permissions": {"$in": permissions}}}
    )
    doc = await db["roles"].find_one({"_id": to_object_id(role_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Role not found")
    return serialize_doc(doc)


@router.delete("/{role_id}", dependencies=[Depends(require_roles("admin"))])
async def delete_role(role_id: str):
    db = get_db()
    result = await db["roles"].delete_one({"_id": to_object_id(role_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"status": "deleted"}
