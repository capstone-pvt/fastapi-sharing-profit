from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def get_profile(user_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    return serialize_doc(doc) if doc else None


async def get_password_hash(user_id: str) -> str | None:
    """Return the raw password hash for verification (not exposed to clients)."""
    db = get_db()
    doc = await db["users"].find_one(
        {"_id": to_object_id(user_id)}, {"password": 1}
    )
    return doc.get("password") if doc else None


async def update_profile(user_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    db = get_db()
    await db["users"].update_one({"_id": to_object_id(user_id)}, {"$set": payload})
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    return serialize_doc(doc) if doc else None


async def update_password(user_id: str, hashed_password: str) -> None:
    db = get_db()
    await db["users"].update_one(
        {"_id": to_object_id(user_id)},
        {"$set": {"password": hashed_password}},
    )


async def update_avatar(user_id: str, image_url: str) -> dict[str, Any] | None:
    db = get_db()
    await db["users"].update_one(
        {"_id": to_object_id(user_id)},
        {"$set": {"profileImageUrl": image_url}},
    )
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    return serialize_doc(doc) if doc else None
