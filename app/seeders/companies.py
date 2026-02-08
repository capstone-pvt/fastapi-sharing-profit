"""Seeder for default company and assigning it to all users."""

from __future__ import annotations

from datetime import datetime

from app.db import get_db

DEFAULT_COMPANY = {
    "companyName": "Default Company",
    "companyCode": "DEFAULT",
    "companyAddress": "",
    "companyPhone": "",
    "companyTaxId": "",
}


async def seed_default_company() -> dict | None:
    """Create default company if it does not exist. Returns the company doc or None."""
    db = get_db()
    now = datetime.utcnow()
    name = DEFAULT_COMPANY["companyName"].strip()
    existing = await db["companies"].find_one(
        {"companyName": {"$regex": f"^{name}$", "$options": "i"}}
    )
    if existing:
        return existing
    doc = {
        **DEFAULT_COMPANY,
        "createdAt": now,
        "updatedAt": now,
    }
    result = await db["companies"].insert_one(doc)
    created = await db["companies"].find_one({"_id": result.inserted_id})
    return created


async def assign_default_company_to_all_users() -> int:
    """Set default company on all users (companyId only). Returns count updated."""
    db = get_db()
    company = await db["companies"].find_one(
        {"companyName": {"$regex": f"^{DEFAULT_COMPANY['companyName']}$", "$options": "i"}}
    )
    if not company:
        return 0
    result = await db["users"].update_many(
        {},
        {
            "$set": {
                "companyId": company["_id"],
                "companyApproved": True,
                "updatedAt": datetime.utcnow(),
            },
            "$unset": {
                "companyName": "",
                "companyCode": "",
                "companyAddress": "",
                "companyPhone": "",
                "companyTaxId": "",
            },
        },
    )
    return result.modified_count


async def seed_default_company_and_assign_to_users() -> tuple[bool, int]:
    """Create default company if missing, then assign it to all users.
    Returns (company_created: bool, users_updated: int).
    """
    existing_before = await get_db()["companies"].count_documents(
        {"companyName": {"$regex": f"^{DEFAULT_COMPANY['companyName']}$", "$options": "i"}}
    )
    company = await seed_default_company()
    created = existing_before == 0 and company is not None
    updated = await assign_default_company_to_all_users()
    return (created, updated)
