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
    get_species_info,
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
    try:
        settings = get_settings()
        if not image:
            raise HTTPException(status_code=400, detail="Image file is required")

        # Read and save image
        try:
            image_bytes = image.file.read()
        except Exception as e:
            print(f"ERROR reading image file: {str(e)}")
            raise HTTPException(status_code=400, detail="Failed to read image file")

        image_name = (
            image.filename
            if image.filename
            else f"analysis_{int(datetime.utcnow().timestamp() * 1000)}.jpg"
        )

        try:
            image_url = save_upload(image_bytes, image_name)
        except Exception as e:
            print(f"ERROR saving image: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to save image")

        # Open and process image
        try:
            pil_image = Image.open(BytesIO(image_bytes)).convert("RGB")
            width, height = pil_image.size
        except Exception as e:
            print(f"ERROR processing image: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid image format")

        # Get active species and detect fish
        try:
            active_species = await list_active_species_names()
        except Exception as e:
            print(f"WARNING: Failed to load active species: {str(e)}")
            active_species = set()

        try:
            detections = detect_fish(pil_image, confidence=confidence, iou=iou)
            print(f"INFO: Detector found {len(detections)} detection(s)")
        except Exception as e:
            print(f"ERROR in fish detection: {str(e)}")
            detections = []

        if active_species:
            detections = [
                detection
                for detection in detections
                if detection.get("species") in active_species
            ]
            print(f"INFO: After filtering by active species: {len(detections)} detection(s)")

        if not detections:
            try:
                species, confidence_score = classify_fish(pil_image)
                print(f"INFO: Classifier returned: {species} with confidence {confidence_score}")
            except Exception as e:
                print(f"ERROR in fish classification: {str(e)}")
                species = "Unknown"
                confidence_score = 0.0

            # If no species detected, create a generic detection for the whole image
            if species == "Unknown" or confidence_score == 0.0:
                print("WARNING: No ML detection/classification. Using fallback: Generic Fish")
                species = "Generic Fish"
                confidence_score = 0.5

            if active_species and species not in active_species and species != "Generic Fish":
                raise HTTPException(
                    status_code=400,
                    detail="No fish detected in the image.",
                )
            detections.append(
                {
                    "id": "det_0",
                    "species": species,
                    "confidence": confidence_score,
                    "boundingBox": {
                        "x": 0.0,
                        "y": 0.0,
                        "width": float(width),
                        "height": float(height),
                    },
                }
            )

        try:
            detections = await apply_estimates_to_detections(
                detections,
                scale_reference_cm=scaleReferenceCm,
                get_species_index=get_species_index,
                get_species_info=get_species_info,
                estimate_weight=estimate_weight,
                estimate_price=estimate_price,
                classify_size=lambda weight: classify_size_by_weight(
                    weight,
                    small_max_kg=settings.size_small_max_kg,
                    medium_max_kg=settings.size_medium_max_kg,
                ),
            )
        except Exception as e:
            print(f"ERROR applying estimates to detections: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to estimate fish properties")

        if singleFish and detections:
            detections = [detections[0]]

        full_name = " ".join(
            part for part in [user.get("firstName"), user.get("lastName")] if part
        ).strip()
        scanned_by = full_name if full_name else user.get("email")

        try:
            analysis = await build_analysis(
                detections,
                user_id=user["id"],
                image_url=image_url,
                scale_reference_cm=scaleReferenceCm,
                single_fish=singleFish,
                image_width=width,
                image_height=height,
                scanned_by=scanned_by,
                get_species_index=get_species_index,
                estimate_price=estimate_price,
            )
        except Exception as e:
            print(f"ERROR building analysis: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to process analysis data")

        try:
            result = await save_analysis(analysis)
            print(f"SUCCESS: Analysis saved with {len(detections)} detection(s)")
            return result
        except Exception as e:
            print(f"ERROR saving analysis: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to save analysis results")

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch any unexpected errors
        print(f"UNEXPECTED ERROR in analyze_fish: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Image analysis failed: {str(e)}"
        )


@router.get("/analytics")
async def analytics(user: dict[str, Any] = Depends(get_current_user)):
    total, mine = await count_analyses(user["id"])
    return {"totalAnalyses": total, "userAnalyses": mine}


@router.get("/analysis-history")
async def analysis_history(user: dict[str, Any] = Depends(get_current_user)):
    return await list_analysis_history(user["id"])
