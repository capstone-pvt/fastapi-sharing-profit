from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def list_users(
    query: dict[str, Any], *, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    db = get_db()
    cursor = db["users"].find(query).skip(offset).limit(limit)
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db["users"].count_documents(query)
    return results, total


async def get_user(user_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    return serialize_doc(doc) if doc else None


async def create_user(payload: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    role_id = payload.pop("roleId", None)
    if role_id:
        payload["role"] = to_object_id(role_id)
    result = await db["users"].insert_one(payload)
    doc = await db["users"].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


async def update_user(user_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    db = get_db()
    role_id = payload.pop("roleId", None)
    if role_id:
        payload["role"] = to_object_id(role_id)
    await db["users"].update_one({"_id": to_object_id(user_id)}, {"$set": payload})
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    return serialize_doc(doc) if doc else None


async def delete_user(user_id: str) -> bool:
    db = get_db()
    result = await db["users"].delete_one({"_id": to_object_id(user_id)})
    return result.deleted_count > 0
