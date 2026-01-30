from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile

from app.core.config import get_settings
from app.deps import get_current_user, require_roles
from app.domain.fish_training_samples.services import (
    build_sample_doc,
    build_samples_query,
)
from app.infrastructure.fish_training_samples.exporter import export_dataset
from app.infrastructure.fish_training_samples.repository import (
    create_sample as repo_create_sample,
    delete_sample as repo_delete_sample,
    list_active_species as repo_list_active_species,
    list_all_samples as repo_list_all_samples,
    list_samples as repo_list_samples,
    list_user_samples as repo_list_user_samples,
)
from app.infrastructure.fish_training_samples.storage import save_training_upload


router = APIRouter(prefix="/fish/training-samples", tags=["fish-training"])


@router.post("")
async def create_sample(
    image: UploadFile = File(...),
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    if not image:
        raise HTTPException(status_code=400, detail="Image file is required")
    settings = get_settings()
    image_path = save_training_upload(
        image, Path(settings.upload_root) / "fish-training"
    )
    image_url = f"/uploads/fish-training/{image_path.name}"
    doc = build_sample_doc(
        payload=payload,
        user_id=user["id"],
        image_path=str(image_path),
        image_url=image_url,
    )
    return await repo_create_sample(doc)


@router.get("", dependencies=[Depends(require_roles("admin"))])
async def list_samples(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    species: str | None = Query(None),
):
    query = build_samples_query(species)
    results, total = await repo_list_samples(query, limit=limit, offset=offset)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/mine")
async def list_my_samples(
    user: dict[str, Any] = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    results, total = await repo_list_user_samples(user["id"], limit=limit, offset=offset)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.post("/export", dependencies=[Depends(require_roles("admin"))])
async def export_dataset(includeImages: bool = Query(True)):
    species_records = await repo_list_active_species()
    samples = await repo_list_all_samples()
    return export_dataset(
        samples=samples,
        species_records=species_records,
        include_images=includeImages,
    )


@router.delete("/{sample_id}", dependencies=[Depends(require_roles("admin"))])
async def delete_sample(sample_id: str):
    deleted = await repo_delete_sample(sample_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Sample not found")
    return {"status": "deleted"}
