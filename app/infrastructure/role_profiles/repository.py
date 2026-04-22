"""MongoDB helpers for role-profile reads/writes. Role-profile data lives on
the user document under `roleProfile.*` so we piggyback on the `users`
collection rather than introducing a new one.
"""
from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def get_user_for_role_profile(user_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    return doc if doc else None


async def update_user_role_profile(
    user_id: str, update: dict[str, Any]
) -> dict[str, Any] | None:
    db = get_db()
    await db["users"].update_one(
        {"_id": to_object_id(user_id)}, {"$set": update}
    )
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    return serialize_doc(doc) if doc else None


async def replace_role_documents(
    user_id: str, documents: list[dict[str, Any]]
) -> dict[str, Any] | None:
    db = get_db()
    await db["users"].update_one(
        {"_id": to_object_id(user_id)},
        {"$set": {"roleProfile.documents": documents}},
    )
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    return serialize_doc(doc) if doc else None


async def list_pending_verification(
    company_object_id: Any | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Users awaiting admin verification:
      - companyApproved is falsy, OR
      - verificationStatus is 'pending' and profileCompleted is True.
    `company_object_id` scopes to a single company (admin view); pass None for
    super-admins who can see every company.
    """
    db = get_db()
    query: dict[str, Any] = {
        "$or": [
            {"companyApproved": False},
            {"companyApproved": {"$exists": False}},
            {"verificationStatus": "pending", "profileCompleted": True},
        ]
    }
    if company_object_id is not None:
        # Match both object and string ids for legacy compat.
        query["companyId"] = {
            "$in": [company_object_id, str(company_object_id)]
        }
    cursor = db["users"].find(query).sort("createdAt", -1).limit(limit)
    docs = [serialize_doc(d) async for d in cursor]
    return docs
