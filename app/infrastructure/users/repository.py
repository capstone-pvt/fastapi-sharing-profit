from __future__ import annotations

from typing import Any

from app.db import get_db
from app.utils import serialize_doc, to_object_id


async def _attach_role_names(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve role IDs to names. Handles both multi-role (roles array)
    and legacy single-role (role/roleId) formats."""
    if not docs:
        return docs
    db = get_db()
    # Collect all unique role IDs across all docs
    all_role_ids: set[str] = set()
    for doc in docs:
        # Multi-role: roles array
        roles_val = doc.get("roles")
        if isinstance(roles_val, list):
            for r in roles_val:
                rid = str(r.get("id") or r.get("_id") or r) if isinstance(r, dict) else str(r)
                if rid:
                    all_role_ids.add(rid)
        else:
            # Legacy single role
            role_value = doc.get("role") or doc.get("roleId")
            if isinstance(role_value, dict):
                role_value = role_value.get("id")
            if isinstance(role_value, str) and role_value:
                all_role_ids.add(role_value)

    if not all_role_ids:
        return docs

    # Batch fetch all roles
    object_ids = [to_object_id(rid) for rid in all_role_ids]
    roles = await db["roles"].find({"_id": {"$in": object_ids}}).to_list(
        length=len(object_ids)
    )
    role_map = {str(role["_id"]): role.get("name") for role in roles}

    # Attach to each doc
    for doc in docs:
        roles_val = doc.get("roles")
        if isinstance(roles_val, list):
            # Multi-role
            roles_array = []
            for r in roles_val:
                rid = str(r.get("id") or r.get("_id") or r) if isinstance(r, dict) else str(r)
                name = role_map.get(rid)
                if rid:
                    roles_array.append({"id": rid, "name": name})
            doc["roles"] = roles_array
            # Backward compat: first role
            if roles_array:
                doc["role"] = roles_array[0]
            doc["roleName"] = roles_array[0]["name"] if roles_array else None
        else:
            # Legacy single role
            role_value = doc.get("role") or doc.get("roleId")
            if isinstance(role_value, dict):
                role_value = role_value.get("id")
            if isinstance(role_value, str) and role_value in role_map:
                doc["role"] = {"id": role_value, "name": role_map[role_value]}
                doc["roles"] = [doc["role"]]
                doc["roleName"] = role_map[role_value]

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
    update_ops: dict[str, Any] = {}

    # Multi-role support
    role_ids = payload.pop("roleIds", None)
    role_id = payload.pop("roleId", None)
    add_role_ids = payload.pop("addRoleIds", None)
    remove_role_ids = payload.pop("removeRoleIds", None)

    if role_ids and isinstance(role_ids, list):
        # Replace all roles
        payload["roles"] = [to_object_id(r) for r in role_ids if r]
    elif role_id:
        # Single role — set as array (backward compat)
        payload["roles"] = [to_object_id(role_id)]

    if payload:
        update_ops["$set"] = payload

    if add_role_ids:
        # Add roles without duplicates
        for rid in add_role_ids:
            update_ops.setdefault("$addToSet", {}).setdefault("roles", {})
            update_ops["$addToSet"]["roles"] = {"$each": [to_object_id(r) for r in add_role_ids]}
            break

    if remove_role_ids:
        update_ops.setdefault("$pull", {})["roles"] = {
            "$in": [to_object_id(r) for r in remove_role_ids]
        }

    if update_ops:
        await db["users"].update_one({"_id": to_object_id(user_id)}, update_ops)

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
