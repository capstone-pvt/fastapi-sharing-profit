from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/fish/species", tags=["fish-species"])


@router.get("", dependencies=[Depends(require_roles("admin"))])
async def list_species():
    db = get_db()
    return [serialize_doc(doc) async for doc in db["fish_species"].find({})]


@router.get("/active", dependencies=[Depends(get_current_user)])
async def list_active_species():
    db = get_db()
    cursor = db["fish_species"].find({"isActive": True}).sort("classIndex", 1)
    return [serialize_doc(doc) async for doc in cursor]


@router.post("", dependencies=[Depends(require_roles("admin"))])
async def create_species(payload: dict[str, Any] = Body(...)):
    db = get_db()
    payload["createdAt"] = datetime.utcnow()
    payload["updatedAt"] = datetime.utcnow()
    result = await db["fish_species"].insert_one(payload)
    doc = await db["fish_species"].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


@router.patch("/{species_id}", dependencies=[Depends(require_roles("admin"))])
async def update_species(species_id: str, payload: dict[str, Any] = Body(...)):
    db = get_db()
    payload["updatedAt"] = datetime.utcnow()
    await db["fish_species"].update_one(
        {"_id": to_object_id(species_id)}, {"$set": payload}
    )
    doc = await db["fish_species"].find_one({"_id": to_object_id(species_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Species not found")
    return serialize_doc(doc)


@router.delete("/{species_id}", dependencies=[Depends(require_roles("admin"))])
async def delete_species(species_id: str):
    db = get_db()
    result = await db["fish_species"].delete_one(
        {"_id": to_object_id(species_id)}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Species not found")
    return {"status": "deleted"}
