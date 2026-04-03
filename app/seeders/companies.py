"""Seeder for default companies."""

from __future__ import annotations

from datetime import datetime, timezone

from app.db import get_db

DEFAULT_COMPANIES = [
    {
        "key": "company_a",
        "companyName": "Blue Ocean Co",
        "companyCode": "BLUE",
        "companyAddress": "",
        "companyPhone": "",
        "companyTaxId": "",
    },
    {
        "key": "company_b",
        "companyName": "Sunrise Fisheries",
        "companyCode": "SUN",
        "companyAddress": "",
        "companyPhone": "",
        "companyTaxId": "",
    },
]


async def seed_default_companies() -> tuple[int, dict[str, dict]]:
    """Create default companies if they do not exist.

    Returns (created_count, companies_by_key).
    """
    db = get_db()
    created_count = 0
    companies_by_key: dict[str, dict] = {}
    for payload in DEFAULT_COMPANIES:
        now = datetime.now(timezone.utc)
        name = payload["companyName"].strip()
        code = (payload.get("companyCode") or "").strip()
        query = {"companyName": {"$regex": f"^{name}$", "$options": "i"}}
        if code:
            query = {"companyCode": {"$regex": f"^{code}$", "$options": "i"}}
        existing = await db["companies"].find_one(query)
        if existing:
            companies_by_key[payload["key"]] = existing
            continue
        doc = {
            "companyName": name,
            "companyCode": code or None,
            "companyAddress": payload.get("companyAddress", ""),
            "companyPhone": payload.get("companyPhone", ""),
            "companyTaxId": payload.get("companyTaxId", ""),
            "createdAt": now,
            "updatedAt": now,
        }
        result = await db["companies"].insert_one(doc)
        created = await db["companies"].find_one({"_id": result.inserted_id})
        if created:
            created_count += 1
            companies_by_key[payload["key"]] = created
    return created_count, companies_by_key
