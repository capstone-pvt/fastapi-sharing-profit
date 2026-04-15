from __future__ import annotations

import re
from typing import Any

from bson import ObjectId

from app.db import get_db
from app.utils import serialize_doc


async def get_species_index(species: str | None) -> int:
    if not species:
        return 0
    db = get_db()
    record = await db["fish_species"].find_one(
        {"name": {"$regex": f"^{re.escape(species)}$", "$options": "i"}}
    )
    if record and record.get("classIndex") is not None:
        return int(record.get("classIndex"))
    return 0


async def get_species_info(species: str | None) -> dict[str, Any] | None:
    """Return full species info including scientific, english, local names,
    and reference data (weight ranges, price ranges, peak months)."""
    if not species:
        return None
    db = get_db()
    record = await db["fish_species"].find_one(
        {"name": {"$regex": f"^{re.escape(species)}$", "$options": "i"}}
    )
    if not record:
        return None
    return {
        "scientificName": record.get("scientificName"),
        "genus": record.get("genus"),
        "family": record.get("family"),
        "englishName": record.get("englishName"),
        "localName": record.get("localName"),
        "weightRange": record.get("weightRange"),
        "pricePerKg": record.get("pricePerKg"),
        "peakMonths": record.get("peakMonths"),
        "habitat": record.get("habitat"),
    }


async def save_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    result = await db["fish_analyses"].insert_one(analysis)
    stored = await db["fish_analyses"].find_one({"_id": result.inserted_id})
    return serialize_doc(stored)


async def count_analyses(user_id: str) -> tuple[int, int]:
    db = get_db()
    total = await db["fish_analyses"].count_documents({})
    mine = await db["fish_analyses"].count_documents({"userId": user_id})
    return total, mine


async def list_analysis_history(
    user_id: str,
    company_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    db = get_db()
    if company_id:
        query: dict[str, Any] = {"companyId": company_id}
    else:
        query = {"userId": user_id}
    total = await db["fish_analyses"].count_documents(query)
    cursor = (
        db["fish_analyses"]
        .find(query)
        .sort("createdAt", -1)
        .skip(offset)
        .limit(limit)
    )
    results = [serialize_doc(doc) async for doc in cursor]
    return results, total


async def list_active_species_names() -> set[str]:
    db = get_db()
    cursor = db["fish_species"].find({"isActive": True})
    return {doc.get("name") async for doc in cursor if doc.get("name")}


async def list_active_species_name_map() -> dict[str, str]:
    """Return a lowercase→original name map for case-insensitive matching."""
    db = get_db()
    cursor = db["fish_species"].find({"isActive": True})
    return {
        doc["name"].lower(): doc["name"]
        async for doc in cursor
        if doc.get("name")
    }


async def get_analysis(analysis_id: str) -> dict[str, Any] | None:
    db = get_db()
    try:
        oid = ObjectId(analysis_id)
    except Exception:
        return None
    doc = await db["fish_analyses"].find_one({"_id": oid})
    return serialize_doc(doc) if doc else None


async def update_analysis(
    analysis_id: str, update: dict[str, Any]
) -> dict[str, Any] | None:
    db = get_db()
    try:
        oid = ObjectId(analysis_id)
    except Exception:
        return None
    await db["fish_analyses"].update_one({"_id": oid}, {"$set": update})
    doc = await db["fish_analyses"].find_one({"_id": oid})
    return serialize_doc(doc) if doc else None
