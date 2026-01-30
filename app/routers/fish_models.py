import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile

from app.core.config import get_settings
from app.db import get_db
from app.deps import require_roles
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/fish/models", tags=["fish-models"])


@router.get("", dependencies=[Depends(require_roles("admin"))])
async def list_models():
    db = get_db()
    return [serialize_doc(doc) async for doc in db["fish_models"].find({})]


@router.get("/active", dependencies=[Depends(require_roles("admin"))])
async def get_active(model_type: str):
    db = get_db()
    doc = await db["fish_models"].find_one({"modelType": model_type, "isActive": True})
    if not doc:
        return None
    return serialize_doc(doc)


@router.post("", dependencies=[Depends(require_roles("admin"))])
async def create_model(payload: dict[str, Any] = Body(...)):
    db = get_db()
    if payload.get("isActive"):
        await db["fish_models"].update_many(
            {"modelType": payload.get("modelType")}, {"$set": {"isActive": False}}
        )
    payload["createdAt"] = datetime.utcnow()
    payload["updatedAt"] = datetime.utcnow()
    result = await db["fish_models"].insert_one(payload)
    doc = await db["fish_models"].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


@router.post("/upload", dependencies=[Depends(require_roles("admin"))])
async def upload_model(
    modelType: str = Body(...),
    version: str = Body(...),
    isActive: str = Body("false"),
    description: str | None = Body(None),
    model: UploadFile = File(...),
):
    settings = get_settings()
    if not model:
        raise HTTPException(status_code=400, detail="Model zip file is required")

    target_dir = (
        Path(settings.model_root) / "registry" / modelType / version
    ).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / "model.zip"
    with zip_path.open("wb") as buffer:
        shutil.copyfileobj(model.file, buffer)

    record = {
        "modelType": modelType,
        "version": version,
        "modelPath": str(zip_path),
        "description": description,
        "isActive": isActive == "true",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    db = get_db()
    if record["isActive"]:
        await db["fish_models"].update_many(
            {"modelType": modelType}, {"$set": {"isActive": False}}
        )
    result = await db["fish_models"].insert_one(record)
    doc = await db["fish_models"].find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


@router.patch("/{model_id}", dependencies=[Depends(require_roles("admin"))])
async def update_model(model_id: str, payload: dict[str, Any] = Body(...)):
    db = get_db()
    if payload.get("isActive"):
        await db["fish_models"].update_many(
            {"modelType": payload.get("modelType")}, {"$set": {"isActive": False}}
        )
    payload["updatedAt"] = datetime.utcnow()
    await db["fish_models"].update_one(
        {"_id": to_object_id(model_id)}, {"$set": payload}
    )
    doc = await db["fish_models"].find_one({"_id": to_object_id(model_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Model not found")
    return serialize_doc(doc)


@router.patch("/{model_id}/activate", dependencies=[Depends(require_roles("admin"))])
async def activate_model(model_id: str):
    db = get_db()
    model = await db["fish_models"].find_one({"_id": to_object_id(model_id)})
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    await db["fish_models"].update_many(
        {"modelType": model.get("modelType")}, {"$set": {"isActive": False}}
    )
    await db["fish_models"].update_one(
        {"_id": to_object_id(model_id)}, {"$set": {"isActive": True}}
    )
    doc = await db["fish_models"].find_one({"_id": to_object_id(model_id)})
    return serialize_doc(doc)
