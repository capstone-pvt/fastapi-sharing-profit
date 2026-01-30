from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def list_models() -> list[dict[str, Any]]:
    db = get_db()
    return [serialize_doc(doc) async for doc in db["fish_models"].find({})]


async def get_active(model_type: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await db["fish_models"].find_one({"modelType": model_type, "isActive": True})
    return serialize_doc(doc) if doc else None


async def create_model(payload: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    if payload.get("isActive"):
        await db["fish_models"].update_many(
            {"modelType": payload.get("modelType")}, {"$set": {"isActive": False}}
        )
    result = await db["fish_models"].insert_one(payload)
    doc = await db["fish_models"].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


async def update_model(
    model_id: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    db = get_db()
    if payload.get("isActive"):
        await db["fish_models"].update_many(
            {"modelType": payload.get("modelType")}, {"$set": {"isActive": False}}
        )
    await db["fish_models"].update_one(
        {"_id": to_object_id(model_id)}, {"$set": payload}
    )
    doc = await db["fish_models"].find_one({"_id": to_object_id(model_id)})
    return serialize_doc(doc) if doc else None


async def activate_model(model_id: str) -> dict[str, Any] | None:
    db = get_db()
    model = await db["fish_models"].find_one({"_id": to_object_id(model_id)})
    if not model:
        return None
    await db["fish_models"].update_many(
        {"modelType": model.get("modelType")}, {"$set": {"isActive": False}}
    )
    await db["fish_models"].update_one(
        {"_id": to_object_id(model_id)}, {"$set": {"isActive": True}}
    )
    doc = await db["fish_models"].find_one({"_id": to_object_id(model_id)})
    return serialize_doc(doc) if doc else None
