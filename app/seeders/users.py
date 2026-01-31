from __future__ import annotations

import re
from datetime import datetime

from app.core.security import hash_password
from app.db import get_db
from app.domain.auth.services import build_user_doc
from app.infrastructure.auth.repository import (
    create_user,
    get_role_by_name,
    get_user_by_email,
)


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


DEFAULT_ROLE_USERS = [
    {
        "role_names": ["Broker/Financer", "Broker/Financier", "Broker"],
        "email": "broker@example.com",
        "first_name": "Broker",
        "last_name": "User",
    },
    {
        "role_names": ["Vessel Owner", "Boat Owner"],
        "email": "vesselowner@example.com",
        "first_name": "Vessel",
        "last_name": "Owner",
    },
    {
        "role_names": ["Fisherman"],
        "email": "fisherman@example.com",
        "first_name": "Fisherman",
        "last_name": "User",
    },
    {
        "role_names": ["Admin"],
        "email": "admin@example.com",
        "first_name": "Admin",
        "last_name": "User",
    },
    {
        "role_names": ["System Admin", "Superadmin", "Super Admin", "Super-Admin"],
        "email": "systemadmin@example.com",
        "first_name": "System",
        "last_name": "Admin",
    },
]


async def seed_default_role_users(
    default_password: str = "Admin@123456",
) -> int:
    db = get_db()
    created = 0
    updated = 0
    for user in DEFAULT_ROLE_USERS:
        role = None
        for role_name in user["role_names"]:
            role = await get_role_by_name(role_name)
            if role:
                break
        if not role:
            continue
        hashed = hash_password(default_password)
        existing = await get_user_by_email(user["email"])
        if existing:
            await db["users"].update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "password": hashed,
                        "role": role["_id"],
                        "updatedAt": datetime.utcnow(),
                    }
                },
            )
            updated += 1
            continue
        user_doc = build_user_doc(
            email=user["email"],
            hashed_password=hashed,
            first_name=user["first_name"],
            last_name=user["last_name"],
            role_id=str(role["_id"]),
        )
        await create_user(user_doc)
        created += 1
    return created + updated
