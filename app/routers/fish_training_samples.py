import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from PIL import Image

from app.core.config import get_settings
from app.db import get_db
from app.deps import get_current_user, require_roles
from app.utils import serialize_doc, to_object_id


router = APIRouter(prefix="/fish/training-samples", tags=["fish-training"])


def _save_upload(file: UploadFile, base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    target = base_dir / f"{int(datetime.utcnow().timestamp() * 1000)}_{file.filename}"
    with target.open("wb") as buffer:
        buffer.write(file.file.read())
    return target


@router.post("")
async def create_sample(
    image: UploadFile = File(...),
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    if not image:
        raise HTTPException(status_code=400, detail="Image file is required")
    settings = get_settings()
    image_path = _save_upload(image, Path(settings.upload_root) / "fish-training")

    doc = {
        "userId": user["id"],
        "imageUrl": f"/uploads/fish-training/{image_path.name}",
        "imagePath": str(image_path),
        "species": payload.get("species"),
        "weightKg": payload.get("weightKg"),
        "pricePerKg": payload.get("pricePerKg"),
        "lengthCm": payload.get("lengthCm"),
        "widthCm": payload.get("widthCm"),
        "scaleReferenceCm": payload.get("scaleReferenceCm"),
        "notes": payload.get("notes"),
        "bbox": None,
        "capturedAt": payload.get("capturedAt"),
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    if all(
        key in payload
        for key in ["bboxX", "bboxY", "bboxWidth", "bboxHeight"]
    ):
        doc["bbox"] = {
            "x": payload.get("bboxX"),
            "y": payload.get("bboxY"),
            "width": payload.get("bboxWidth"),
            "height": payload.get("bboxHeight"),
        }

    db = get_db()
    result = await db["fish_training_samples"].insert_one(doc)
    stored = await db["fish_training_samples"].find_one(
        {"_id": result.inserted_id}
    )
    return serialize_doc(stored)


@router.get("", dependencies=[Depends(require_roles("admin"))])
async def list_samples(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    species: str | None = Query(None),
):
    db = get_db()
    query: dict[str, Any] = {}
    if species:
        query["species"] = species
    cursor = db["fish_training_samples"].find(query).skip(offset).limit(limit)
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db["fish_training_samples"].count_documents(query)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.get("/mine")
async def list_my_samples(
    user: dict[str, Any] = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    query = {"userId": user["id"]}
    cursor = db["fish_training_samples"].find(query).skip(offset).limit(limit)
    results = [serialize_doc(doc) async for doc in cursor]
    total = await db["fish_training_samples"].count_documents(query)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


@router.post("/export", dependencies=[Depends(require_roles("admin"))])
async def export_dataset(includeImages: bool = Query(True)):
    db = get_db()
    timestamp = int(datetime.utcnow().timestamp() * 1000)
    export_root = Path("exports") / "fish-training" / str(timestamp)
    images_dir = export_root / "images"
    labels_dir = export_root / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    species_records = [doc async for doc in db["fish_species"].find({"isActive": True})]
    class_index_by_name = {
        record.get("name"): record.get("classIndex")
        for record in species_records
    }

    samples = [doc async for doc in db["fish_training_samples"].find({})]
    if not class_index_by_name:
        unique_species = sorted({s.get("species") for s in samples if s.get("species")})
        class_index_by_name = {name: idx for idx, name in enumerate(unique_species)}

    weight_rows = [
        "image,species,classIndex,weightKg,pricePerKg,lengthCm,widthCm,scaleReferenceCm,bboxX,bboxY,bboxWidth,bboxHeight"
    ]
    price_rows = ["image,species,classIndex,weightKg,pricePerKg"]
    images_count = 0
    labels_count = 0
    price_samples = 0

    for sample in samples:
        image_path = Path(sample.get("imagePath", ""))
        if not image_path.exists():
            continue
        ext = image_path.suffix or ".jpg"
        image_file = f"{sample['_id']}{ext}"
        dest_image = images_dir / image_file

        if includeImages:
            dest_image.write_bytes(image_path.read_bytes())
            images_count += 1

        class_index = class_index_by_name.get(sample.get("species"), -1)
        bbox = sample.get("bbox") or {}
        bbox_x = bbox_y = bbox_w = bbox_h = ""
        if bbox and class_index >= 0:
            with Image.open(image_path) as img:
                width, height = img.size
            if width and height:
                x_center = (bbox["x"] + bbox["width"] / 2) / width
                y_center = (bbox["y"] + bbox["height"] / 2) / height
                width_norm = bbox["width"] / width
                height_norm = bbox["height"] / height
                label_line = f"{class_index} {x_center:.6f} {y_center:.6f} {width_norm:.6f} {height_norm:.6f}"
                (labels_dir / f"{sample['_id']}.txt").write_text(label_line + "\n")
                labels_count += 1
                bbox_x = str(bbox["x"])
                bbox_y = str(bbox["y"])
                bbox_w = str(bbox["width"])
                bbox_h = str(bbox["height"])

        weight_rows.append(
            ",".join(
                [
                    image_file,
                    str(sample.get("species") or ""),
                    str(class_index),
                    str(sample.get("weightKg") or ""),
                    str(sample.get("pricePerKg") or ""),
                    str(sample.get("lengthCm") or ""),
                    str(sample.get("widthCm") or ""),
                    str(sample.get("scaleReferenceCm") or ""),
                    bbox_x,
                    bbox_y,
                    bbox_w,
                    bbox_h,
                ]
            )
        )
        if sample.get("pricePerKg") is not None:
            price_rows.append(
                ",".join(
                    [
                        image_file,
                        str(sample.get("species") or ""),
                        str(class_index),
                        str(sample.get("weightKg") or ""),
                        str(sample.get("pricePerKg") or ""),
                    ]
                )
            )
            price_samples += 1

    (export_root / "weight_data.csv").write_text("\n".join(weight_rows) + "\n")
    (export_root / "price_data.csv").write_text("\n".join(price_rows) + "\n")
    classes = [
        name for name, _ in sorted(class_index_by_name.items(), key=lambda x: x[1])
    ]
    (export_root / "classes.txt").write_text("\n".join(classes) + "\n")
    (export_root / "manifest.json").write_text(
        json.dumps(
            {
                "createdAt": datetime.utcnow().isoformat(),
                "samples": len(samples),
                "images": images_count,
                "labels": labels_count,
                "priceSamples": price_samples,
                "classes": classes,
                "exportRoot": str(export_root),
            },
            indent=2,
        )
    )

    return {
        "exportRoot": str(export_root),
        "samples": len(samples),
        "images": images_count,
        "labels": labels_count,
        "priceSamples": price_samples,
        "classes": classes,
    }


@router.delete("/{sample_id}", dependencies=[Depends(require_roles("admin"))])
async def delete_sample(sample_id: str):
    db = get_db()
    result = await db["fish_training_samples"].delete_one(
        {"_id": to_object_id(sample_id)}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Sample not found")
    return {"status": "deleted"}
