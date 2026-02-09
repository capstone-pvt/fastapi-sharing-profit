from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from app.db import get_db
from app.deps import get_current_user, require_permissions
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

    if "read" in allowed_actions:
        @router.get("", dependencies=_deps("read"))
        async def list_items(
            request: Request,
            limit: int = Query(50, ge=1, le=500),
            offset: int = Query(0, ge=0),
        ):
            db = get_db()
            query: dict[str, Any] = {}
            for key, value in request.query_params.items():
                if key in {"limit", "offset"}:
                    continue
                query[key] = value
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
        async def get_item(item_id: str):
            db = get_db()
            doc = await db[collection_name].find_one(
                {"_id": to_object_id(item_id)}
            )
            if not doc:
                raise HTTPException(status_code=404, detail="Not found")
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
            company_name = user.get("companyName")
            if company_name:
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
            payload["updatedAt"] = datetime.utcnow()
            await db[collection_name].update_one(
                {"_id": to_object_id(item_id)}, {"$set": payload}
            )
            doc = await db[collection_name].find_one(
                {"_id": to_object_id(item_id)}
            )
            if not doc:
                raise HTTPException(status_code=404, detail="Not found")
            return serialize_doc(doc)

    if "delete" in allowed_actions:
        @router.delete("/{item_id}", dependencies=_deps("delete"))
        async def delete_item(item_id: str):
            db = get_db()
            result = await db[collection_name].delete_one(
                {"_id": to_object_id(item_id)}
            )
            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Not found")
            return {"status": "deleted"}

    return router
