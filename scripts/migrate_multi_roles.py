"""Migrate user documents from single-role to multi-role format.

Converts:
  role: ObjectId("abc")   →  roles: [ObjectId("abc")]
  roleId: "abc"           →  roles: [ObjectId("abc")]

Idempotent — safe to run multiple times.
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.db import connect_db, disconnect_db, get_db
from app.utils import to_object_id


async def migrate():
    await connect_db()
    db = get_db()
    col = db["users"]

    # Count current state
    total = await col.count_documents({})
    already_migrated = await col.count_documents({"roles": {"$exists": True, "$type": "array"}})
    has_single_role = await col.count_documents({"role": {"$exists": True}, "roles": {"$exists": False}})
    has_role_id = await col.count_documents({
        "role": {"$exists": False},
        "roles": {"$exists": False},
        "roleId": {"$exists": True},
    })
    has_nothing = total - already_migrated - has_single_role - has_role_id

    print(f"Total users:          {total}")
    print(f"Already migrated:     {already_migrated}")
    print(f"Has 'role' (single):  {has_single_role}")
    print(f"Has 'roleId' (str):   {has_role_id}")
    print(f"No role field:        {has_nothing}")
    print()

    migrated = 0

    # 1. Convert single role: ObjectId → roles array
    async for user in col.find({"role": {"$exists": True}, "roles": {"$exists": False}}):
        role_val = user.get("role")
        if isinstance(role_val, list):
            continue  # already an array somehow
        roles_array = [role_val] if role_val else []
        await col.update_one(
            {"_id": user["_id"]},
            {"$set": {"roles": roles_array}, "$unset": {"role": ""}},
        )
        migrated += 1

    # 2. Convert roleId string → roles array
    async for user in col.find({
        "role": {"$exists": False},
        "roles": {"$exists": False},
        "roleId": {"$exists": True},
    }):
        rid = user.get("roleId")
        try:
            roles_array = [to_object_id(rid)] if rid else []
        except Exception:
            roles_array = []
        await col.update_one(
            {"_id": user["_id"]},
            {"$set": {"roles": roles_array}, "$unset": {"roleId": ""}},
        )
        migrated += 1

    # 3. Users with no role at all — set empty array
    result = await col.update_many(
        {"roles": {"$exists": False}},
        {"$set": {"roles": []}},
    )
    migrated += result.modified_count

    print(f"Migrated: {migrated} user(s)")

    # Verify
    final = await col.count_documents({"roles": {"$exists": True, "$type": "array"}})
    print(f"Verification: {final}/{total} users now have 'roles' array")

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(migrate())
