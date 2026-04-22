from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import re

from bson import ObjectId
from bson.errors import InvalidId

from app.core.cache import AsyncTtlCache
from app.db import get_db
from app.utils import serialize_doc, to_object_id


# Roles change rarely; cache full role docs by id for 2 minutes to avoid
# re-fetching them on every authenticated list request (e.g. via _is_super_user).
_role_doc_cache = AsyncTtlCache(ttl_seconds=120.0)


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


async def _load_role_doc(role_id: str) -> dict[str, Any] | None:
    db = get_db()
    try:
        object_id = to_object_id(role_id)
    except InvalidId:
        return None
    doc = await db["roles"].find_one({"_id": object_id})
    return serialize_doc(doc) if doc else None


async def get_role(role_id: str) -> dict[str, Any] | None:
    return await _role_doc_cache.get_or_set(
        role_id, lambda rid=role_id: _load_role_doc(rid)
    )


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
    _role_doc_cache.invalidate(role_id)
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
    _role_doc_cache.invalidate(role_id)
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
    _role_doc_cache.invalidate(role_id)
    doc = await db["roles"].find_one({"_id": object_id})
    return serialize_doc(doc) if doc else None


async def delete_role(role_id: str) -> bool:
    db = get_db()
    try:
        object_id = to_object_id(role_id)
    except InvalidId:
        return False
    result = await db["roles"].delete_one({"_id": object_id})
    _role_doc_cache.invalidate(role_id)
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
            if isinstance(perm, ObjectId) or ObjectId.is_valid(str(perm))
        ]
        cursor = db["permissions"].find({"_id": {"$in": ids}})
        return [perm.get("name") async for perm in cursor if perm.get("name")]
    return [str(perm) for perm in role_perms]


async def ensure_default_roles(
    role_permissions: dict[str, list[str]] | None = None,
) -> None:
    db = get_db()
    now = datetime.now(timezone.utc)

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
    from pymongo import UpdateOne

    # Bulk upsert all default roles
    bulk_ops = [
        UpdateOne(
            {"name": payload["name"]},
            {"$setOnInsert": payload},
            upsert=True,
        )
        for payload in defaults
    ]
    if bulk_ops:
        await db["roles"].bulk_write(bulk_ops, ordered=False)

    if role_permissions:
        perm_ops = [
            UpdateOne(
                {"name": role_name},
                {
                    "$set": {
                        "permissions": [
                            to_object_id(pid) if isinstance(pid, str) else pid
                            for pid in permissions
                        ],
                        "updatedAt": now,
                    },
                },
            )
            for role_name, permissions in role_permissions.items()
            if permissions
        ]
        if perm_ops:
            await db["roles"].bulk_write(perm_ops, ordered=False)
