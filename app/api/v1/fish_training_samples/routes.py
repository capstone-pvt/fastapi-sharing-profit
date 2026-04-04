from pathlib import Path
import os
import subprocess
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)

from app.core.config import get_settings
from app.deps import get_current_user, require_permissions, require_roles
from app.domain.fish_training_samples.services import (
    build_sample_doc,
    build_samples_query,
)
from app.infrastructure.fish_training_samples import exporter as training_exporter
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


def _auto_train_enabled() -> bool:
    value = os.getenv("AUTO_TRAIN_ON_SAMPLE", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _launch_auto_train() -> None:
    project_root = Path(__file__).resolve().parents[4]
    args = os.getenv("AUTO_TRAIN_ARGS", "").strip()
    cmd = ["python", "scripts/auto_train.py"]
    if args:
        cmd.extend(args.split())
    subprocess.Popen(cmd, cwd=str(project_root))


@router.post("", dependencies=[Depends(require_permissions("training-samples:create"))])
async def create_sample(
    image: UploadFile = File(...),
    species: str | None = Form(None),
    scientificName: str | None = Form(None),
    englishName: str | None = Form(None),
    localName: str | None = Form(None),
    weightKg: float | None = Form(None),
    pricePerKg: float | None = Form(None),
    lengthCm: float | None = Form(None),
    widthCm: float | None = Form(None),
    scaleReferenceCm: float | None = Form(None),
    bboxX: float | None = Form(None),
    bboxY: float | None = Form(None),
    bboxWidth: float | None = Form(None),
    bboxHeight: float | None = Form(None),
    notes: str | None = Form(None),
    capturedAt: str | None = Form(None),
    user: dict[str, Any] = Depends(get_current_user),
):
    if not image:
        raise HTTPException(status_code=400, detail="Image file is required")

    # Validate required fields BEFORE saving the file to avoid orphan uploads
    if not species or weightKg is None:
        raise HTTPException(
            status_code=400,
            detail="species and weightKg are required",
        )

    settings = get_settings()
    image_path = save_training_upload(
        image, Path(settings.upload_root) / "fish-training"
    )
    image_url = f"/uploads/fish-training/{image_path.name}"
    full_name = " ".join(
        part for part in [user.get("firstName"), user.get("lastName")] if part
    ).strip()
    trained_by = full_name if full_name else user.get("email")
    payload = {
        "species": species,
        "scientificName": scientificName,
        "englishName": englishName,
        "localName": localName,
        "weightKg": weightKg,
        "pricePerKg": pricePerKg,
        "lengthCm": lengthCm,
        "widthCm": widthCm,
        "scaleReferenceCm": scaleReferenceCm,
        "bboxX": bboxX,
        "bboxY": bboxY,
        "bboxWidth": bboxWidth,
        "bboxHeight": bboxHeight,
        "notes": notes,
        "capturedAt": capturedAt,
    }

    doc = build_sample_doc(
        payload=payload,
        user_id=user["id"],
        image_path=str(image_path),
        image_url=image_url,
        trained_by=trained_by,
    )
    return await repo_create_sample(doc)


@router.get("", dependencies=[Depends(require_permissions("training-samples:read"))])
async def list_samples(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    species: str | None = Query(None),
):
    query = build_samples_query(species)
    results, total = await repo_list_samples(query, limit=limit, offset=offset)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/mine", dependencies=[Depends(require_permissions("training-samples:read"))])
async def list_my_samples(
    user: dict[str, Any] = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    results, total = await repo_list_user_samples(user["id"], limit=limit, offset=offset)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.post("/export", dependencies=[Depends(require_roles("admin"))])
async def export_training_samples(
    includeImages: bool = Query(True),
    background_tasks: BackgroundTasks = None,
):
    species_records = await repo_list_active_species()
    samples = await repo_list_all_samples()
    result = training_exporter.export_dataset(
        samples=samples,
        species_records=species_records,
        include_images=includeImages,
    )
    if background_tasks is not None and _auto_train_enabled():
        background_tasks.add_task(_launch_auto_train)
    return result


@router.delete("/{sample_id}", dependencies=[Depends(require_roles("admin"))])
async def delete_sample(sample_id: str):
    deleted = await repo_delete_sample(sample_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Sample not found")
    return {"status": "deleted"}
