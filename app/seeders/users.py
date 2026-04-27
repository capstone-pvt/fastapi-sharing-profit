from __future__ import annotations

import re
from datetime import datetime, timezone

from app.core.security import hash_password
from app.db import get_db
from app.domain.auth.services import build_user_doc
from app.infrastructure.auth.repository import (
    create_user,
    get_role_by_name,
    get_user_by_email,
)
from app.infrastructure.roles.repository import RoleNames
from app.seeders.companies import DEFAULT_COMPANIES


async def backfill_default_user_role() -> int:
    db = get_db()
    role = await db["roles"].find_one(
        {"name": {"$regex": f"^{RoleNames.USER}$", "$options": "i"}}
    )
    if not role:
        return 0
    role_id = role["_id"]
    result = await db["users"].update_many(
        {"$and": [
            {"roles": {"$exists": False}},
            {"$or": [{"role": {"$exists": False}}, {"role": None}]},
        ]},
        {"$set": {"roles": [role_id]}},
    )
    return result.modified_count


DEFAULT_ROLE_USERS = [
    {
        "role_names": [RoleNames.SUPER],
        "email": "super@demo.com",
        "first_name": "Super",
        "last_name": "Admin",
    },
    {
        "role_names": [RoleNames.ADMIN],
        "email": "admin@demo.com",
        "first_name": "Admin",
        "last_name": "User",
        "company_key": "company_a",
    },
    {
        "role_names": [RoleNames.BROKER],
        "email": "broker@demo.com",
        "first_name": "Broker",
        "last_name": "Demo",
        "company_key": "company_a",
    },
    {
        "role_names": [RoleNames.OWNER],
        "email": "owner@demo.com",
        "first_name": "Owner",
        "last_name": "Demo",
        "company_key": "company_a",
    },
    {
        "role_names": [RoleNames.CREW],
        "email": "crew@demo.com",
        "first_name": "Crew",
        "last_name": "Demo",
        "company_key": "company_a",
    },
    {
        # Government regulator (Port Management Unit / BFAR / LGU). No
        # company_key — government users are cross-company readers and
        # don't belong to any single company.
        "role_names": [RoleNames.GOVERNMENT],
        "email": "gov@demo.com",
        "first_name": "Government",
        "last_name": "Admin",
    },
]


async def seed_default_role_users(
    default_password: str = "P@ssw0rd123",
) -> int:
    db = get_db()
    created = 0
    updated = 0
    company_lookup: dict[str, dict] = {}
    for company in DEFAULT_COMPANIES:
        key = company.get("key")
        code = (company.get("companyCode") or "").strip()
        name = (company.get("companyName") or "").strip()
        query = {"companyName": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
        if code:
            query = {"companyCode": {"$regex": f"^{re.escape(code)}$", "$options": "i"}}
        company_doc = await db["companies"].find_one(query)
        if key and company_doc:
            company_lookup[key] = company_doc
    for user in DEFAULT_ROLE_USERS:
        role = None
        for role_name in user["role_names"]:
            role = await get_role_by_name(role_name)
            if role:
                break
        if not role:
            continue
        company_doc = None
        company_key = user.get("company_key")
        if company_key:
            company_doc = company_lookup.get(company_key)
        company_id = str(company_doc["_id"]) if company_doc else None
        hashed = hash_password(default_password)
        existing = await get_user_by_email(user["email"])
        if existing:
            # Don't overwrite roles if user already has multi-role array
            existing_roles = existing.get("roles")
            has_multi_roles = isinstance(existing_roles, list) and len(existing_roles) > 1
            update_fields = {
                "password": hashed,
                "updatedAt": datetime.now(timezone.utc),
                "companyApproved": True,
            }
            if not has_multi_roles:
                update_fields["roles"] = [role["_id"]]
            unset_fields: dict[str, str] = {
                "companyName": "",
                "companyCode": "",
                "companyAddress": "",
                "companyPhone": "",
                "companyTaxId": "",
            }
            # Only set companyId if user doesn't already have one
            existing_company = existing.get("companyId")
            if not existing_company and company_doc:
                update_fields["companyId"] = company_doc["_id"]
            await db["users"].update_one(
                {"_id": existing["_id"]},
                {
                    "$set": update_fields,
                    "$unset": unset_fields,
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
            company_id=company_id,
        )
        user_doc["companyApproved"] = True
        await create_user(user_doc)
        created += 1
    return created + updated
