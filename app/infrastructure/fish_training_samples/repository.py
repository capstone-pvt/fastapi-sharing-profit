from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def create_sample(payload: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    result = await db["fish_training_samples"].insert_one(payload)
    stored = await db["fish_training_samples"].find_one({"_id": result.inserted_id})
    return serialize_doc(stored)


async def list_samples(
    query: dict[str, Any], *, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    db = get_db()
    cursor = db["fish_training_samples"].find(query).skip(offset).limit(limit)
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db["fish_training_samples"].count_documents(query)
    return results, total


async def list_user_samples(
    user_id: str, *, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    db = get_db()
    query = {"userId": user_id}
    cursor = db["fish_training_samples"].find(query).skip(offset).limit(limit)
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db["fish_training_samples"].count_documents(query)
    return results, total


async def list_all_samples() -> list[dict[str, Any]]:
    db = get_db()
    return [doc async for doc in db["fish_training_samples"].find({})]


async def list_active_species() -> list[dict[str, Any]]:
    db = get_db()
    return [doc async for doc in db["fish_species"].find({"isActive": True})]


async def delete_sample(sample_id: str) -> bool:
    db = get_db()
    result = await db["fish_training_samples"].delete_one(
        {"_id": to_object_id(sample_id)}
    )
    return result.deleted_count > 0
