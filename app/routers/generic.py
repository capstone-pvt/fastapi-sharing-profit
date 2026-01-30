from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from app.db import get_db
from app.utils import serialize_doc, to_object_id


def build_crud_router(collection_name: str) -> APIRouter:
    router = APIRouter()

    @router.get("")
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
        cursor = db[collection_name].find(query).skip(offset).limit(limit)
        results = [serialize_doc(doc) async for doc in cursor]
        total = await db[collection_name].count_documents(query)
        return {"results": results, "total": total, "limit": limit, "offset": offset}

    @router.get("/{item_id}")
    async def get_item(item_id: str):
        db = get_db()
        doc = await db[collection_name].find_one({"_id": to_object_id(item_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Not found")
        return serialize_doc(doc)

    @router.post("")
    async def create_item(payload: dict[str, Any] = Body(...)):
        db = get_db()
        payload["createdAt"] = datetime.utcnow()
        payload["updatedAt"] = datetime.utcnow()
        result = await db[collection_name].insert_one(payload)
        doc = await db[collection_name].find_one({"_id": result.inserted_id})
        return serialize_doc(doc)

    @router.patch("/{item_id}")
    async def update_item(item_id: str, payload: dict[str, Any] = Body(...)):
        db = get_db()
        payload["updatedAt"] = datetime.utcnow()
        await db[collection_name].update_one(
            {"_id": to_object_id(item_id)}, {"$set": payload}
        )
        doc = await db[collection_name].find_one({"_id": to_object_id(item_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Not found")
        return serialize_doc(doc)

    @router.delete("/{item_id}")
    async def delete_item(item_id: str):
        db = get_db()
        result = await db[collection_name].delete_one({"_id": to_object_id(item_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Not found")
        return {"status": "deleted"}

    return router
