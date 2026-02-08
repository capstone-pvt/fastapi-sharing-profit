from __future__ import annotations

from datetime import datetime
from typing import Any
import re

from bson import ObjectId
from bson.errors import InvalidId

from app.db import get_db
from app.utils import serialize_doc, to_object_id


# Role name constants
class RoleNames:
    USER = "user"
    BROKER = "broker"
    OWNER = "owner"
    CREW = "crew"
    ADMIN = "admin"
    SUPER = "super"


async def list_roles() -> list[dict[str, Any]]:
    db = get_db()
    return [serialize_doc(doc) async for doc in db["roles"].find({})]


async def get_role(role_id: str) -> dict[str, Any] | None:
    db = get_db()
    try:
        object_id = to_object_id(role_id)
    except InvalidId:
        return None
    doc = await db["roles"].find_one({"_id": object_id})
    return serialize_doc(doc) if doc else None


async def create_role(payload: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    result = await db["roles"].insert_one(payload)
    doc = await db["roles"].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


async def update_role(role_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    db = get_db()
    try:
        object_id = to_object_id(role_id)
    except InvalidId:
        return None
    await db["roles"].update_one({"_id": object_id}, {"$set": payload})
    doc = await db["roles"].find_one({"_id": object_id})
    return serialize_doc(doc) if doc else None


async def add_permissions(role_id: str, permissions: list[str]) -> dict[str, Any] | None:
    db = get_db()
    try:
        object_id = to_object_id(role_id)
    except InvalidId:
        return None
    await db["roles"].update_one(
        {"_id": object_id},
        {"$addToSet": {"permissions": {"$each": permissions}}},
    )
    doc = await db["roles"].find_one({"_id": object_id})
    return serialize_doc(doc) if doc else None


async def remove_permissions(
    role_id: str, permissions: list[str]
) -> dict[str, Any] | None:
    db = get_db()
    try:
        object_id = to_object_id(role_id)
    except InvalidId:
        return None
    await db["roles"].update_one(
        {"_id": object_id}, {"$pull": {"permissions": {"$in": permissions}}}
    )
    doc = await db["roles"].find_one({"_id": object_id})
    return serialize_doc(doc) if doc else None


async def delete_role(role_id: str) -> bool:
    db = get_db()
    try:
        object_id = to_object_id(role_id)
    except InvalidId:
        return False
    result = await db["roles"].delete_one({"_id": object_id})
    return result.deleted_count > 0


async def get_role_permissions_names(role_id: str) -> list[str]:
    db = get_db()
    try:
        object_id = to_object_id(role_id)
    except InvalidId:
        return []
    role = await db["roles"].find_one({"_id": object_id})
    if not role:
        return []
    role_perms = role.get("permissions", [])
    if not role_perms:
        return []
    if isinstance(role_perms[0], dict) and "name" in role_perms[0]:
        return [perm.get("name") for perm in role_perms if perm.get("name")]
    has_object_ids = any(
        isinstance(perm, ObjectId) or ObjectId.is_valid(str(perm))
        for perm in role_perms
    )
    if has_object_ids:
        ids = [
            perm if isinstance(perm, ObjectId) else to_object_id(str(perm))
            for perm in role_perms
        ]
        cursor = db["permissions"].find({"_id": {"$in": ids}})
        return [perm.get("name") async for perm in cursor if perm.get("name")]
    return [str(perm) for perm in role_perms]


async def ensure_default_roles(
    role_permissions: dict[str, list[str]] | None = None,
) -> None:
    db = get_db()
    now = datetime.utcnow()
    defaults = [
        {
            "name": RoleNames.USER,
            "description": "Default user role",
            "permissions": [],
            "isActive": True,
            "createdAt": now,
            "updatedAt": now,
        },
        {
            "name": RoleNames.BROKER,
            "description": "Broker or financer role",
            "permissions": [],
            "isActive": True,
            "createdAt": now,
            "updatedAt": now,
        },
        {
            "name": RoleNames.OWNER,
            "description": "Vessel owner role",
            "permissions": [],
            "isActive": True,
            "createdAt": now,
            "updatedAt": now,
        },
        {
            "name": RoleNames.CREW,
            "description": "Crew member role",
            "permissions": [],
            "isActive": True,
            "createdAt": now,
            "updatedAt": now,
        },
        {
            "name": RoleNames.ADMIN,
            "description": "Administrator role with elevated permissions",
            "permissions": [],
            "isActive": True,
            "createdAt": now,
            "updatedAt": now,
        },
        {
            "name": RoleNames.SUPER,
            "description": "Super administrator role with all permissions",
            "permissions": [],
            "isActive": True,
            "createdAt": now,
            "updatedAt": now,
        },
    ]
    for payload in defaults:
        name = payload["name"]
        await db["roles"].update_one(
            {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
            {"$setOnInsert": payload},
            upsert=True,
        )

    if role_permissions:
        for role_name, permissions in role_permissions.items():
            if not permissions:
                continue
            await db["roles"].update_one(
                {"name": {"$regex": f"^{re.escape(role_name)}$", "$options": "i"}},
                {
                    "$addToSet": {"permissions": {"$each": permissions}},
                    "$set": {"updatedAt": now},
                },
            )
