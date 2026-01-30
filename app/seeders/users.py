from __future__ import annotations

import re

from app.db import get_db


async def backfill_default_user_role() -> int:
    db = get_db()
    role = await db["roles"].find_one(
        {"name": {"$regex": r"^User$", "$options": "i"}}
    )
    if not role:
        return 0
    role_id = role["_id"]
    result = await db["users"].update_many(
        {"$or": [{"role": {"$exists": False}}, {"role": None}]},
        {"$set": {"role": role_id}},
    )
    return result.modified_count
