from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def create_sample(payload: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    result = await db["fish_training_samples"].insert_one(payload)
    stored = await db["fish_training_samples"].find_one({"_id": result.inserted_id})
    return serialize_doc(stored)


async def list_samples(
    query: dict[str, Any], *, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    db = get_db()
    cursor = db["fish_training_samples"].find(query).skip(offset).limit(limit)
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db["fish_training_samples"].count_documents(query)
    return results, total


async def list_user_samples(
    user_id: str, *, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    db = get_db()
    query = {"userId": user_id}
    cursor = db["fish_training_samples"].find(query).skip(offset).limit(limit)
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db["fish_training_samples"].count_documents(query)
    return results, total


async def list_all_samples() -> list[dict[str, Any]]:
    db = get_db()
    return [serialize_doc(doc) async for doc in db["fish_training_samples"].find({})]


async def list_active_species() -> list[dict[str, Any]]:
    db = get_db()
    return [serialize_doc(doc) async for doc in db["fish_species"].find({"isActive": True})]


async def delete_sample(sample_id: str) -> bool:
    db = get_db()
    result = await db["fish_training_samples"].delete_one(
        {"_id": to_object_id(sample_id)}
    )
    return result.deleted_count > 0


async def update_sample(
    sample_id: str, update_fields: dict[str, Any]
) -> dict[str, Any] | None:
    db = get_db()
    from datetime import datetime, timezone

    update_fields["updatedAt"] = datetime.now(timezone.utc)
    await db["fish_training_samples"].update_one(
        {"_id": to_object_id(sample_id)}, {"$set": update_fields}
    )
    doc = await db["fish_training_samples"].find_one(
        {"_id": to_object_id(sample_id)}
    )
    return serialize_doc(doc) if doc else None


async def get_correction_stats() -> dict[str, Any]:
    db = get_db()
    col = db["fish_training_samples"]

    total_samples = await col.count_documents({})
    total_corrections = await col.count_documents({"source": "scanner_correction"})
    pending_review = await col.count_documents(
        {"source": "scanner_correction", "reviewStatus": {"$exists": False}}
    )
    approved = await col.count_documents(
        {"source": "scanner_correction", "reviewStatus": "approved"}
    )
    rejected = await col.count_documents(
        {"source": "scanner_correction", "reviewStatus": "rejected"}
    )

    # Aggregate corrections by species (what AI got wrong → what user corrected to)
    pipeline = [
        {"$match": {"source": "scanner_correction"}},
        {
            "$group": {
                "_id": {
                    "correctedTo": "$species",
                    "originalSpecies": "$originalSpecies",
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    by_species = []
    async for doc in col.aggregate(pipeline):
        by_species.append(
            {
                "correctedTo": doc["_id"].get("correctedTo"),
                "originalSpecies": doc["_id"].get("originalSpecies"),
                "count": doc["count"],
            }
        )

    # Last correction timestamp
    last_cursor = (
        col.find({"source": "scanner_correction"}, {"createdAt": 1})
        .sort("createdAt", -1)
        .limit(1)
    )
    last_correction_at = None
    async for doc in last_cursor:
        last_correction_at = doc.get("createdAt")

    return {
        "totalSamples": total_samples,
        "totalCorrections": total_corrections,
        "pendingReview": pending_review,
        "approved": approved,
        "rejected": rejected,
        "correctionsBySpecies": by_species,
        "lastCorrectionAt": (
            last_correction_at.isoformat() if last_correction_at else None
        ),
    }
