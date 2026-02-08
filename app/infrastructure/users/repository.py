from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def _attach_role_names(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not docs:
        return docs
    db = get_db()
    role_ids: list[str] = []
    for doc in docs:
        role_value = doc.get("role") or doc.get("roleId")
        if isinstance(role_value, dict):
            role_value = role_value.get("id")
        if isinstance(role_value, str) and role_value:
            role_ids.append(role_value)
    if not role_ids:
        return docs
    unique_ids = list({role_id for role_id in role_ids})
    object_ids = [to_object_id(role_id) for role_id in unique_ids]
    roles = await db["roles"].find({"_id": {"$in": object_ids}}).to_list(
        length=len(object_ids)
    )
    role_map = {str(role["_id"]): role.get("name") for role in roles}
    for doc in docs:
        role_value = doc.get("role") or doc.get("roleId")
        if isinstance(role_value, dict):
            role_value = role_value.get("id")
        if isinstance(role_value, str) and role_value in role_map:
            doc["role"] = {"id": role_value, "name": role_map[role_value]}
    return docs


async def _attach_company_info(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not docs:
        return docs
    db = get_db()
    company_ids: list[str] = []
    for doc in docs:
        cid = doc.get("companyId")
        if cid:
            company_ids.append(str(cid))
    if not company_ids:
        return docs
    unique_ids = list({cid for cid in company_ids})
    object_ids = [to_object_id(cid) for cid in unique_ids]
    companies = await db["companies"].find({"_id": {"$in": object_ids}}).to_list(
        length=len(object_ids)
    )
    company_map = {
        str(c["_id"]): {
            "companyName": c.get("companyName"),
            "companyAddress": c.get("companyAddress"),
            "companyPhone": c.get("companyPhone"),
            "companyTaxId": c.get("companyTaxId"),
        }
        for c in companies
    }
    for doc in docs:
        cid = doc.get("companyId")
        if cid and str(cid) in company_map:
            info = company_map[str(cid)]
            doc["companyName"] = info["companyName"]
            doc["companyAddress"] = info["companyAddress"]
            doc["companyPhone"] = info["companyPhone"]
            doc["companyTaxId"] = info["companyTaxId"]
    return docs


async def list_users(
    query: dict[str, Any], *, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    db = get_db()
    cursor = db["users"].find(query).skip(offset).limit(limit)
    results = [serialize_doc(doc) async for doc in cursor]
    results = await _attach_role_names(results)
    results = await _attach_company_info(results)
    total = await db["users"].count_documents(query)
    return results, total


async def get_user(user_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    if not doc:
        return None
    result = serialize_doc(doc)
    results = await _attach_role_names([result])
    results = await _attach_company_info(results)
    return results[0] if results else result


async def create_user(payload: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    role_id = payload.pop("roleId", None)
    if role_id:
        payload["role"] = to_object_id(role_id)
    result = await db["users"].insert_one(payload)
    doc = await db["users"].find_one({"_id": result.inserted_id})
    result_doc = serialize_doc(doc) if doc else {}
    results = await _attach_role_names([result_doc])
    results = await _attach_company_info(results)
    return results[0] if results else result_doc


async def update_user(user_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    db = get_db()
    role_id = payload.pop("roleId", None)
    if role_id:
        payload["role"] = to_object_id(role_id)
    await db["users"].update_one({"_id": to_object_id(user_id)}, {"$set": payload})
    doc = await db["users"].find_one({"_id": to_object_id(user_id)})
    if not doc:
        return None
    result_doc = serialize_doc(doc)
    results = await _attach_role_names([result_doc])
    results = await _attach_company_info(results)
    return results[0] if results else result_doc


async def delete_user(user_id: str) -> bool:
    db = get_db()
    result = await db["users"].delete_one({"_id": to_object_id(user_id)})
    return result.deleted_count > 0
