from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile

from app.deps import require_roles
from app.domain.fish_models.services import (
    build_create_model_payload,
    build_update_model_payload,
    build_upload_record,
)
from app.infrastructure.fish_models.repository import (
    activate_model as repo_activate_model,
    create_model as repo_create_model,
    get_active as repo_get_active,
    list_models as repo_list_models,
    update_model as repo_update_model,
)
from app.infrastructure.fish_models.storage import save_model_zip


router = APIRouter(prefix="/fish/models", tags=["fish-models"])


@router.get("", dependencies=[Depends(require_roles("admin"))])
async def list_models():
    return await repo_list_models()


@router.get("/active", dependencies=[Depends(require_roles("admin"))])
async def get_active(model_type: str):
    return await repo_get_active(model_type)


@router.post("", dependencies=[Depends(require_roles("admin"))])
async def create_model(payload: dict[str, Any] = Body(...)):
    model_payload = build_create_model_payload(payload)
    return await repo_create_model(model_payload)


@router.post("/upload", dependencies=[Depends(require_roles("admin"))])
async def upload_model(
    modelType: str = Body(...),
    version: str = Body(...),
    isActive: str = Body("false"),
    description: str | None = Body(None),
    model: UploadFile = File(...),
):
    if not model:
        raise HTTPException(status_code=400, detail="Model zip file is required")

    zip_path = save_model_zip(modelType, version, model.file)
    record = build_upload_record(
        model_type=modelType,
        version=version,
        description=description,
        is_active=isActive == "true",
        model_path=str(zip_path),
    )
    return await repo_create_model(record)


@router.patch("/{model_id}", dependencies=[Depends(require_roles("admin"))])
async def update_model(model_id: str, payload: dict[str, Any] = Body(...)):
    model_payload = build_update_model_payload(payload)
    doc = await repo_update_model(model_id, model_payload)
    if not doc:
        raise HTTPException(status_code=404, detail="Model not found")
    return doc


@router.patch("/{model_id}/activate", dependencies=[Depends(require_roles("admin"))])
async def activate_model(model_id: str):
    doc = await repo_activate_model(model_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Model not found")
    return doc


@router.delete("/{model_id}", dependencies=[Depends(require_roles("admin"))])
async def delete_model(
    model_id: str, status: str = Query("cancelled", pattern="^(cancelled|rejected)$")
):
    model_payload = build_update_model_payload(
        {"status": status, "isActive": False}
    )
    doc = await repo_update_model(model_id, model_payload)
    if not doc:
        raise HTTPException(status_code=404, detail="Model not found")
    return doc
