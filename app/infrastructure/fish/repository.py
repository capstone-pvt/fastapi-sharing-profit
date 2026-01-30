from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import serialize_doc


async def get_species_index(species: str | None) -> int:
    if not species:
        return 0
    db = get_db()
    record = await db["fish_species"].find_one({"name": species})
    if record and record.get("classIndex") is not None:
        return int(record.get("classIndex"))
    return 0


async def save_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    result = await db["fish_analyses"].insert_one(analysis)
    stored = await db["fish_analyses"].find_one({"_id": result.inserted_id})
    return serialize_doc(stored)


async def count_analyses(user_id: str) -> tuple[int, int]:
    db = get_db()
    total = await db["fish_analyses"].count_documents({})
    mine = await db["fish_analyses"].count_documents({"userId": user_id})
    return total, mine


async def list_analysis_history(user_id: str) -> list[dict[str, Any]]:
    db = get_db()
    cursor = db["fish_analyses"].find({"userId": user_id}).sort("createdAt", -1)
    return [serialize_doc(doc) async for doc in cursor]


async def list_active_species_names() -> set[str]:
    db = get_db()
    cursor = db["fish_species"].find({"isActive": True})
    return {doc.get("name") async for doc in cursor if doc.get("name")}
