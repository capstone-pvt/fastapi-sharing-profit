from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from app.db import get_db
from app.deps import get_current_user, require_permissions
from app.infrastructure.roles.repository import get_role
from app.utils import serialize_doc, to_object_id


def build_crud_router(
    collection_name: str,
    permissions: dict[str, str] | None = None,
    allowed_actions: set[str] | None = None,
) -> APIRouter:
    router = APIRouter()
    permissions = permissions or {}
    allowed_actions = allowed_actions or {"create", "read", "update", "delete"}

    def _deps(action: str) -> list:
        perm = permissions.get(action)
        return [Depends(require_permissions(perm))] if perm else []

    async def _get_role_name(user: dict[str, Any]) -> str:
        role_value = user.get("role")
        if isinstance(role_value, dict):
            role_name = role_value.get("name")
            if role_name:
                return str(role_name)
            role_value = role_value.get("id")
        if not role_value:
            role_value = user.get("roleId")
        if not role_value:
            return ""
        role = await get_role(str(role_value))
        return str(role.get("name") or "") if role else ""

    async def _is_super_user(user: dict[str, Any]) -> bool:
        role_name = (await _get_role_name(user)).strip().lower()
        return role_name == "super"

    def _company_id_value(data: dict[str, Any]) -> str | None:
        company_id = data.get("companyId")
        return str(company_id) if company_id else None

    def _company_object_id(company_id: str | None) -> Any | None:
        if not company_id:
            return None
        try:
            return to_object_id(company_id)
        except Exception:
            return None

    if "read" in allowed_actions:
        @router.get("", dependencies=_deps("read"))
        async def list_items(
            request: Request,
            limit: int = Query(50, ge=1, le=500),
            offset: int = Query(0, ge=0),
            user: dict[str, Any] = Depends(get_current_user),
        ):
            db = get_db()
            query: dict[str, Any] = {}
            for key, value in request.query_params.items():
                if key in {"limit", "offset"}:
                    continue
                query[key] = value
            if not await _is_super_user(user):
                company_id = _company_id_value(user)
                object_id = _company_object_id(company_id)
                if not object_id:
                    return {
                        "results": [],
                        "total": 0,
                        "limit": limit,
                        "offset": offset,
                    }
                query["companyId"] = {"$in": [object_id, str(object_id)]}
            cursor = (
                db[collection_name]
                .find(query)
                .sort("createdAt", -1)
                .skip(offset)
                .limit(limit)
            )
            results = [serialize_doc(doc) async for doc in cursor]
            total = await db[collection_name].count_documents(query)
            return {
                "results": results,
                "total": total,
                "limit": limit,
                "offset": offset,
            }

        @router.get("/{item_id}", dependencies=_deps("read"))
        async def get_item(
            item_id: str,
            user: dict[str, Any] = Depends(get_current_user),
        ):
            db = get_db()
            doc = await db[collection_name].find_one(
                {"_id": to_object_id(item_id)}
            )
            if not doc:
                raise HTTPException(status_code=404, detail="Not found")
            if not await _is_super_user(user):
                company_id = _company_id_value(user)
                target_company_id = _company_id_value(doc)
                if not company_id or company_id != target_company_id:
                    raise HTTPException(status_code=403, detail="Forbidden")
            return serialize_doc(doc)

    if "create" in allowed_actions:
        @router.post("", dependencies=_deps("create"))
        async def create_item(
            payload: dict[str, Any] = Body(...),
            user: dict[str, Any] = Depends(get_current_user),
        ):
            db = get_db()
            payload["createdAt"] = datetime.utcnow()
            payload["updatedAt"] = datetime.utcnow()
            is_super = await _is_super_user(user)
            if not is_super:
                company_id = _company_id_value(user)
                object_id = _company_object_id(company_id)
                if not object_id:
                    raise HTTPException(status_code=403, detail="Company not set")
                payload["companyId"] = object_id
            elif payload.get("companyId"):
                object_id = _company_object_id(str(payload["companyId"]))
                if not object_id:
                    raise HTTPException(status_code=400, detail="Invalid companyId")
                payload["companyId"] = object_id
            company_name = user.get("companyName")
            if company_name and not is_super:
                payload["companyName"] = company_name
            result = await db[collection_name].insert_one(payload)
            doc = await db[collection_name].find_one({"_id": result.inserted_id})
            return serialize_doc(doc)

    if "update" in allowed_actions:
        @router.patch("/{item_id}", dependencies=_deps("update"))
        async def update_item(
            item_id: str,
            payload: dict[str, Any] = Body(...),
            user: dict[str, Any] = Depends(get_current_user),
        ):
            db = get_db()
            payload.pop("companyName", None)
            is_super = await _is_super_user(user)
            if not is_super:
                payload.pop("companyId", None)
            elif payload.get("companyId"):
                object_id = _company_object_id(str(payload["companyId"]))
                if not object_id:
                    raise HTTPException(status_code=400, detail="Invalid companyId")
                payload["companyId"] = object_id
            payload["updatedAt"] = datetime.utcnow()
            doc = await db[collection_name].find_one(
                {"_id": to_object_id(item_id)}
            )
            if not doc:
                raise HTTPException(status_code=404, detail="Not found")
            if not is_super:
                company_id = _company_id_value(user)
                target_company_id = _company_id_value(doc)
                if not company_id or company_id != target_company_id:
                    raise HTTPException(status_code=403, detail="Forbidden")
            await db[collection_name].update_one(
                {"_id": to_object_id(item_id)}, {"$set": payload}
            )
            doc = await db[collection_name].find_one(
                {"_id": to_object_id(item_id)}
            )
            return serialize_doc(doc)

    if "delete" in allowed_actions:
        @router.delete("/{item_id}", dependencies=_deps("delete"))
        async def delete_item(
            item_id: str,
            user: dict[str, Any] = Depends(get_current_user),
        ):
            db = get_db()
            if not await _is_super_user(user):
                doc = await db[collection_name].find_one(
                    {"_id": to_object_id(item_id)}
                )
                if not doc:
                    raise HTTPException(status_code=404, detail="Not found")
                company_id = _company_id_value(user)
                target_company_id = _company_id_value(doc)
                if not company_id or company_id != target_company_id:
                    raise HTTPException(status_code=403, detail="Forbidden")
            result = await db[collection_name].delete_one(
                {"_id": to_object_id(item_id)}
            )
            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Not found")
            return {"status": "deleted"}

    return router
