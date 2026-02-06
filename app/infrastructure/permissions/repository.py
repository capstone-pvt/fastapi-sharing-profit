from __future__ import annotations

from datetime import datetime
from typing import Any
import re

from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def list_permissions() -> list[dict[str, Any]]:
    db = get_db()
    return [serialize_doc(doc) async for doc in db["permissions"].find({})]


async def get_permission(perm_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await db["permissions"].find_one({"_id": to_object_id(perm_id)})
    return serialize_doc(doc) if doc else None


async def create_permission(payload: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    result = await db["permissions"].insert_one(payload)
    doc = await db["permissions"].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


async def update_permission(
    perm_id: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    db = get_db()
    await db["permissions"].update_one(
        {"_id": to_object_id(perm_id)}, {"$set": payload}
    )
    doc = await db["permissions"].find_one({"_id": to_object_id(perm_id)})
    return serialize_doc(doc) if doc else None


async def delete_permission(perm_id: str) -> bool:
    db = get_db()
    result = await db["permissions"].delete_one({"_id": to_object_id(perm_id)})
    return result.deleted_count > 0


async def ensure_default_permissions() -> dict[str, str]:
    db = get_db()
    now = datetime.utcnow()
    defaults = [
        {
            "name": "vessels:create",
            "resource": "vessels",
            "action": "create",
            "description": "Create vessels",
        },
        {
            "name": "vessels:read",
            "resource": "vessels",
            "action": "read",
            "description": "View vessels",
        },
        {
            "name": "vessels:update",
            "resource": "vessels",
            "action": "update",
            "description": "Update vessels",
        },
        {
            "name": "vessels:delete",
            "resource": "vessels",
            "action": "delete",
            "description": "Delete vessels",
        },
        {
            "name": "boats:create",
            "resource": "boats",
            "action": "create",
            "description": "Create boats",
        },
        {
            "name": "boats:read",
            "resource": "boats",
            "action": "read",
            "description": "View boats",
        },
        {
            "name": "boats:update",
            "resource": "boats",
            "action": "update",
            "description": "Update boats",
        },
        {
            "name": "boats:delete",
            "resource": "boats",
            "action": "delete",
            "description": "Delete boats",
        },
        {
            "name": "boats:create",
            "resource": "boats",
            "action": "create",
            "description": "Create boats",
        },
        {
            "name": "boats:read",
            "resource": "boats",
            "action": "read",
            "description": "View boats",
        },
        {
            "name": "boats:update",
            "resource": "boats",
            "action": "update",
            "description": "Update boats",
        },
        {
            "name": "boats:delete",
            "resource": "boats",
            "action": "delete",
            "description": "Delete boats",
        },
        {
            "name": "vessel-owners:create",
            "resource": "vessel-owners",
            "action": "create",
            "description": "Create vessel owners",
        },
        {
            "name": "vessel-owners:read",
            "resource": "vessel-owners",
            "action": "read",
            "description": "View vessel owners",
        },
        {
            "name": "vessel-owners:update",
            "resource": "vessel-owners",
            "action": "update",
            "description": "Update vessel owners",
        },
        {
            "name": "vessel-owners:delete",
            "resource": "vessel-owners",
            "action": "delete",
            "description": "Delete vessel owners",
        },
        {
            "name": "trips:create",
            "resource": "trips",
            "action": "create",
            "description": "Create trips",
        },
        {
            "name": "trips:read",
            "resource": "trips",
            "action": "read",
            "description": "View trips",
        },
        {
            "name": "trips:update",
            "resource": "trips",
            "action": "update",
            "description": "Update trips",
        },
        {
            "name": "trips:delete",
            "resource": "trips",
            "action": "delete",
            "description": "Delete trips",
        },
        {
            "name": "fish-sales:create",
            "resource": "fish-sales",
            "action": "create",
            "description": "Capture and input fish sales",
        },
        {
            "name": "fish-sales:read",
            "resource": "fish-sales",
            "action": "read",
            "description": "View fish sales",
        },
        {
            "name": "fish-sales:update",
            "resource": "fish-sales",
            "action": "update",
            "description": "Update fish sales",
        },
        {
            "name": "fish-sales:delete",
            "resource": "fish-sales",
            "action": "delete",
            "description": "Delete fish sales",
        },
        {
            "name": "expenses:create",
            "resource": "expenses",
            "action": "create",
            "description": "Record expenses",
        },
        {
            "name": "expenses:read",
            "resource": "expenses",
            "action": "read",
            "description": "View expenses",
        },
        {
            "name": "expenses:update",
            "resource": "expenses",
            "action": "update",
            "description": "Update expenses",
        },
        {
            "name": "expenses:delete",
            "resource": "expenses",
            "action": "delete",
            "description": "Delete expenses",
        },
        {
            "name": "cash-advances:read",
            "resource": "cash-advances",
            "action": "read",
            "description": "View cash advances",
        },
        {
            "name": "cash-advances:approve",
            "resource": "cash-advances",
            "action": "approve",
            "description": "Approve cash advances",
        },
        {
            "name": "cash-advances:decline",
            "resource": "cash-advances",
            "action": "decline",
            "description": "Decline cash advances",
        },
        {
            "name": "training-samples:create",
            "resource": "training-samples",
            "action": "create",
            "description": "Upload training samples",
        },
        {
            "name": "training-samples:read",
            "resource": "training-samples",
            "action": "read",
            "description": "View training samples",
        },
        {
            "name": "user:create",
            "resource": "users",
            "action": "create",
            "description": "Create users",
        },
        {
            "name": "user:read",
            "resource": "users",
            "action": "read",
            "description": "View users",
        },
        {
            "name": "user:update",
            "resource": "users",
            "action": "update",
            "description": "Update users",
        },
        {
            "name": "user:delete",
            "resource": "users",
            "action": "delete",
            "description": "Delete users",
        },
        {
            "name": "companies:read",
            "resource": "companies",
            "action": "read",
            "description": "View companies",
        },
        {
            "name": "companies:create",
            "resource": "companies",
            "action": "create",
            "description": "Create companies",
        },
        {
            "name": "companies:update",
            "resource": "companies",
            "action": "update",
            "description": "Update companies",
        },
        {
            "name": "companies:delete",
            "resource": "companies",
            "action": "delete",
            "description": "Delete companies",
        },
        {
            "name": "forecasts:read",
            "resource": "forecasts",
            "action": "read",
            "description": "View forecasts and predictions",
        },
        {
            "name": "forecasts:create",
            "resource": "forecasts",
            "action": "create",
            "description": "Create forecasts and predictions",
        },
        {
            "name": "forecasts:update",
            "resource": "forecasts",
            "action": "update",
            "description": "Update forecasts and predictions",
        },
        {
            "name": "forecasts:delete",
            "resource": "forecasts",
            "action": "delete",
            "description": "Delete forecasts and predictions",
        },
        {
            "name": "forecasts:create",
            "resource": "forecasts",
            "action": "create",
            "description": "Create forecasts and predictions",
        },
        {
            "name": "forecasts:update",
            "resource": "forecasts",
            "action": "update",
            "description": "Update forecasts and predictions",
        },
        {
            "name": "forecasts:delete",
            "resource": "forecasts",
            "action": "delete",
            "description": "Delete forecasts and predictions",
        },
        {
            "name": "fishermen:create",
            "resource": "fishermen",
            "action": "create",
            "description": "Create fishermen",
        },
        {
            "name": "fishermen:read",
            "resource": "fishermen",
            "action": "read",
            "description": "View fishermen",
        },
        {
            "name": "fishermen:update",
            "resource": "fishermen",
            "action": "update",
            "description": "Update fishermen",
        },
        {
            "name": "fishermen:delete",
            "resource": "fishermen",
            "action": "delete",
            "description": "Delete fishermen",
        },
        {
            "name": "catches:create",
            "resource": "catches",
            "action": "create",
            "description": "Input individual fish catches",
        },
        {
            "name": "catches:read",
            "resource": "catches",
            "action": "read",
            "description": "View fish catches",
        },
        {
            "name": "catches:update",
            "resource": "catches",
            "action": "update",
            "description": "Update fish catches",
        },
        {
            "name": "catches:delete",
            "resource": "catches",
            "action": "delete",
            "description": "Delete fish catches",
        },
        {
            "name": "profit-sharing-policies:create",
            "resource": "profit-sharing-policies",
            "action": "create",
            "description": "Create profit sharing policies",
        },
        {
            "name": "profit-sharing-policies:read",
            "resource": "profit-sharing-policies",
            "action": "read",
            "description": "View profit sharing policies",
        },
        {
            "name": "profit-sharing-policies:update",
            "resource": "profit-sharing-policies",
            "action": "update",
            "description": "Update profit sharing policies",
        },
        {
            "name": "profit-sharing-policies:delete",
            "resource": "profit-sharing-policies",
            "action": "delete",
            "description": "Delete profit sharing policies",
        },
        {
            "name": "profit-shares:generate",
            "resource": "profit-shares",
            "action": "generate",
            "description": "Generate profit shares",
        },
        {
            "name": "profit-shares:read",
            "resource": "profit-shares",
            "action": "read",
            "description": "View profit shares",
        },
        {
            "name": "cash-advances:create",
            "resource": "cash-advances",
            "action": "create",
            "description": "Request cash advances",
        },
        {
            "name": "cash-advances:update",
            "resource": "cash-advances",
            "action": "update",
            "description": "Update cash advance requests",
        },
    ]
    permission_ids: dict[str, str] = {}
    for perm in defaults:
        name = perm["name"]
        payload = {
            **perm,
            "createdAt": now,
            "updatedAt": now,
        }
        await db["permissions"].update_one(
            {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
            {"$setOnInsert": payload},
            upsert=True,
        )
        doc = await db["permissions"].find_one(
            {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
        )
        if doc:
            permission_ids[name] = str(doc["_id"])
    return permission_ids
