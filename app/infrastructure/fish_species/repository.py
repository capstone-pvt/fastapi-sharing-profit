from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def list_species() -> list[dict[str, Any]]:
    db = get_db()
    return [serialize_doc(doc) async for doc in db["fish_species"].find({})]


async def list_active_species() -> list[dict[str, Any]]:
    db = get_db()
    cursor = db["fish_species"].find({"isActive": True}).sort("classIndex", 1)
    return [serialize_doc(doc) async for doc in cursor]


async def create_species(payload: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    result = await db["fish_species"].insert_one(payload)
    doc = await db["fish_species"].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


async def update_species(
    species_id: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    db = get_db()
    await db["fish_species"].update_one(
        {"_id": to_object_id(species_id)}, {"$set": payload}
    )
    doc = await db["fish_species"].find_one({"_id": to_object_id(species_id)})
    return serialize_doc(doc) if doc else None


async def delete_species(species_id: str) -> bool:
    db = get_db()
    result = await db["fish_species"].delete_one(
        {"_id": to_object_id(species_id)}
    )
    return result.deleted_count > 0
