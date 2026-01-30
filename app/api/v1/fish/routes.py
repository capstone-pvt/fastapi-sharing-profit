from datetime import datetime
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image

from app.deps import get_current_user
from app.domain.fish.services import (
    apply_estimates_to_detections,
    build_analysis,
    classify_size_by_weight,
)
from app.infrastructure.fish.inference import (
    classify_fish,
    detect_fish,
    estimate_price,
    estimate_weight,
)
from app.core.config import get_settings
from app.infrastructure.fish.repository import (
    count_analyses,
    get_species_index,
    list_analysis_history,
    list_active_species_names,
    save_analysis,
)
from app.infrastructure.fish.storage import save_upload


router = APIRouter(prefix="/fish", tags=["fish"])


@router.post("/analyze")
async def analyze_fish(
    image: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
    singleFish: bool | None = None,
    scaleReferenceCm: float | None = None,
    confidence: float | None = None,
    iou: float | None = None,
):
    settings = get_settings()
    if not image:
        raise HTTPException(status_code=400, detail="Image file is required")
    image_bytes = image.file.read()
    image_name = (
        image.filename
        if image.filename
        else f"analysis_{int(datetime.utcnow().timestamp() * 1000)}.jpg"
    )
    image_url = save_upload(image_bytes, image_name)
    pil_image = Image.open(BytesIO(image_bytes)).convert("RGB")
    width, height = pil_image.size

    active_species = await list_active_species_names()
    detections = detect_fish(pil_image, confidence=confidence, iou=iou)
    if active_species:
        detections = [
            detection
            for detection in detections
            if detection.get("species") in active_species
        ]

    if not detections:
        species, confidence = classify_fish(pil_image)
        if active_species and species not in active_species:
            raise HTTPException(
                status_code=400,
                detail="No fish detected in the image.",
            )
        detections.append(
            {
                "id": "det_0",
                "species": species,
                "confidence": confidence,
                "boundingBox": {
                    "x": 0.0,
                    "y": 0.0,
                    "width": float(width),
                    "height": float(height),
                },
            }
        )

    detections = await apply_estimates_to_detections(
        detections,
        scale_reference_cm=scaleReferenceCm,
        get_species_index=get_species_index,
        estimate_weight=estimate_weight,
        estimate_price=estimate_price,
        classify_size=lambda weight: classify_size_by_weight(
            weight,
            small_max_kg=settings.size_small_max_kg,
            medium_max_kg=settings.size_medium_max_kg,
        ),
    )

    if singleFish and detections:
        detections = [detections[0]]

    analysis = await build_analysis(
        detections,
        user_id=user["id"],
        image_url=image_url,
        scale_reference_cm=scaleReferenceCm,
        single_fish=singleFish,
        get_species_index=get_species_index,
        estimate_price=estimate_price,
    )
    return await save_analysis(analysis)


@router.get("/analytics")
async def analytics(user: dict[str, Any] = Depends(get_current_user)):
    total, mine = await count_analyses(user["id"])
    return {"totalAnalyses": total, "userAnalyses": mine}


@router.get("/analysis-history")
async def analysis_history(user: dict[str, Any] = Depends(get_current_user)):
    return await list_analysis_history(user["id"])
