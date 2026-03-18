from datetime import datetime
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from PIL import Image

from app.deps import get_current_user, require_permissions
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
    list_active_species_name_map,
    save_analysis,
)
from app.infrastructure.fish.storage import save_upload
from app.infrastructure.roles.repository import get_role


router = APIRouter(prefix="/fish", tags=["fish"])


async def _get_role_name(user: dict[str, Any]) -> str:
    role_id = user.get("roleId")
    if not role_id:
        return ""
    role = await get_role(str(role_id))
    return (role.get("name") or "").strip().lower() if role else ""


@router.post("/analyze")
async def analyze_fish(
    image: UploadFile = File(...),
    user: dict[str, Any] = Depends(require_permissions("fish:analyze")),
    singleFish: bool | None = None,
    scaleReferenceCm: float | None = None,
    confidence: float | None = None,
    iou: float | None = None,
    caughtBy: str | None = None,
    caughtByName: str | None = None,
):
    try:
        settings = get_settings()
        if not image:
            raise HTTPException(status_code=400, detail="Image file is required")

        # Read and save image
        try:
            image_bytes = await image.read()
            if not image_bytes:
                print("ERROR: image.read() returned empty bytes")
                raise HTTPException(status_code=400, detail="Image file is empty")
        except HTTPException:
            raise
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

        # Get active species (case-insensitive map: lowercase -> canonical name)
        species_map: dict[str, str] = {}
        try:
            species_map = await list_active_species_name_map()
            print(f"INFO: Loaded {len(species_map)} active species from DB")
        except Exception as e:
            print(f"WARNING: Failed to load active species: {str(e)}")

        # Known typos / aliases in model class names
        _SPECIES_ALIASES = {"tune": "tuna"}

        def _normalize_species(name: str) -> str:
            """Map model species name to canonical DB name (case-insensitive)."""
            key = name.lower()
            key = _SPECIES_ALIASES.get(key, key)
            return species_map.get(key, name)

        print(f"INFO: Image size={pil_image.size}, mode={pil_image.mode}, bytes={len(image_bytes)}")
        try:
            detections = detect_fish(pil_image, confidence=confidence, iou=iou)
            print(f"INFO: Detector found {len(detections)} detection(s)")
        except Exception as e:
            print(f"ERROR in fish detection: {str(e)}")
            detections = []

        # Normalize species names from model to match DB names
        for det in detections:
            det["species"] = _normalize_species(det.get("species", "Unknown"))

        if species_map:
            canonical_names = set(species_map.values())
            detections = [
                detection
                for detection in detections
                if detection.get("species") in canonical_names
            ]
            print(f"INFO: After filtering by active species: {len(detections)} detection(s)")

        if not detections:
            try:
                species, confidence_score = classify_fish(pil_image)
                species = _normalize_species(species)
                print(f"INFO: Classifier returned: {species} with confidence {confidence_score}")
            except Exception as e:
                import traceback
                print(f"ERROR in fish classification: {str(e)}")
                traceback.print_exc()
                species = "Unknown"
                confidence_score = 0.0

            # If no species detected, create a generic detection for the whole image
            if species == "Unknown" or confidence_score == 0.0:
                print("WARNING: No ML detection/classification. Using fallback: Generic Fish")
                species = "Generic Fish"
                confidence_score = 0.5

            canonical_names = set(species_map.values()) if species_map else set()
            if canonical_names and species not in canonical_names and species != "Generic Fish":
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

        # Resolve company ID for scoping
        company_id = user.get("companyId")
        if company_id:
            company_id = str(company_id)

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
                caught_by=caughtBy,
                caught_by_name=caughtByName,
                company_id=company_id,
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


@router.get("/diagnostic")
async def diagnostic(user: dict[str, Any] = Depends(require_permissions("fish:diagnostic"))):
    """Diagnostic endpoint to verify model loading and species DB."""
    import os
    from PIL import Image

    settings = get_settings()
    result = {"models": {}, "species": {}, "testPrediction": {}}

    # Check model files
    for name, path in [
        ("detector", settings.detector_model_path),
        ("classifier", settings.classifier_model_path),
        ("weight", settings.weight_model_path),
        ("price", settings.price_model_path),
    ]:
        result["models"][name] = {
            "path": path,
            "exists": os.path.exists(path),
        }

    # Check species in DB
    species_map = await list_active_species_name_map()
    result["species"]["count"] = len(species_map)
    result["species"]["names"] = sorted(species_map.values())

    # Test model loading and prediction with a blank image
    test_img = Image.new("RGB", (640, 480), color="blue")
    try:
        detections = detect_fish(test_img, confidence=0.25, iou=0.45)
        result["testPrediction"]["detector"] = {
            "status": "ok",
            "detections": len(detections),
        }
    except Exception as e:
        result["testPrediction"]["detector"] = {"status": "error", "error": str(e)}

    try:
        species, conf = classify_fish(test_img)
        result["testPrediction"]["classifier"] = {
            "status": "ok",
            "species": species,
            "confidence": conf,
        }
    except Exception as e:
        result["testPrediction"]["classifier"] = {"status": "error", "error": str(e)}

    return result


@router.get("/analytics")
async def analytics(user: dict[str, Any] = Depends(require_permissions("fish:analytics"))):
    total, mine = await count_analyses(user["id"])
    return {"totalAnalyses": total, "userAnalyses": mine}


@router.get("/analysis-history")
async def analysis_history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(require_permissions("fish:history")),
):
    role_name = await _get_role_name(user)

    company_id = None
    if role_name in ("broker", "admin", "super", "owner"):
        cid = user.get("companyId")
        if cid:
            company_id = str(cid)

    results, total = await list_analysis_history(
        user_id=user["id"],
        company_id=company_id,
        limit=limit,
        offset=offset,
    )
    return {
        "results": results,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
