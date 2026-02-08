from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def get_user_by_email(email: str) -> dict[str, Any] | None:
    db = get_db()
    return await db["users"].find_one({"email": email})


async def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    db = get_db()
    return await db["users"].find_one({"_id": to_object_id(user_id)})


async def get_role_by_id(role_id: str) -> dict[str, Any] | None:
    db = get_db()
    return await db["roles"].find_one({"_id": to_object_id(role_id)})


async def get_role_by_name(name: str) -> dict[str, Any] | None:
    db = get_db()
    return await db["roles"].find_one(
        {"name": {"$regex": f"^{name}$", "$options": "i"}}
    )


async def create_user(user_doc: dict[str, Any]) -> str:
    db = get_db()
    role_id = user_doc.pop("roleId", None)
    if role_id:
        user_doc["role"] = to_object_id(role_id)
    company_id = user_doc.pop("companyId", None)
    if company_id:
        user_doc["companyId"] = to_object_id(company_id)
    result = await db["users"].insert_one(user_doc)
    return str(result.inserted_id)


async def get_company_by_id(company_id: str) -> dict[str, Any] | None:
    db = get_db()
    try:
        return await db["companies"].find_one({"_id": to_object_id(company_id)})
    except Exception:
        return None


async def get_company_by_code(company_code: str) -> dict[str, Any] | None:
    if not (company_code or "").strip():
        return None
    db = get_db()
    code = (company_code or "").strip()
    return await db["companies"].find_one(
        {"companyCode": {"$regex": f"^{code}$", "$options": "i"}}
    )


async def update_refresh_token(
    user_id: str, refresh_token: str | None, refresh_expiry: datetime | None
) -> None:
    db = get_db()
    await db["users"].update_one(
        {"_id": to_object_id(user_id)},
        {"$set": {"refreshToken": refresh_token, "refreshTokenExpiry": refresh_expiry}},
    )

async def update_session(
    user_id: str,
    refresh_token: str | None,
    refresh_expiry: datetime | None,
    session_id: str | None,
) -> None:
    db = get_db()
    await db["users"].update_one(
        {"_id": to_object_id(user_id)},
        {
            "$set": {
                "refreshToken": refresh_token,
                "refreshTokenExpiry": refresh_expiry,
                "sessionId": session_id,
            }
        },
    )

async def revoke_refresh_token(user_id: str) -> None:
    await update_session(user_id, None, None, None)


async def serialize_user(user: dict[str, Any]) -> dict[str, Any]:
    return serialize_doc(user)
