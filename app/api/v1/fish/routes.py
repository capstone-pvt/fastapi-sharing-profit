import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Callable

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from PIL import Image

from app.deps import get_current_user, require_permissions

logger = logging.getLogger(__name__)
from app.domain.fish.services import (
    apply_estimates_to_detections,
    build_analysis,
    classify_size_by_weight,
)
from app.infrastructure.fish.inference import (
    classify_fish,
    classify_fish_top_n,
    detect_fish,
    estimate_price,
    estimate_weight,
    preprocess_image,
    verify_detections_with_classifier,
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

_ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Known typos / aliases in model class names -> canonical names
_SPECIES_ALIASES: dict[str, str] = {
    "tune": "tuna",
    "tunas": "tuna",
    "milkfish": "bangus",
    "tilapiia": "tilapia",
    "galunggong": "galunggong",
    "round scad": "galunggong",
    "sardinas": "sardines",
    "sardine": "sardines",
    "tamban": "sardines",
    "alumahan": "alumahan",
    "indian mackerel": "alumahan",
    "dalagang-bukid": "dalagang bukid",
    "lapu lapu": "lapu-lapu",
    "lapulapu": "lapu-lapu",
    "grouper": "lapu-lapu",
    "maya maya": "maya-maya",
    "mayamaya": "maya-maya",
    "red snapper": "maya-maya",
    "tanigue": "tanigue",
    "spanish mackerel": "tanigue",
    "bangos": "bangus",
    "salmon": "salmon",
    "pompano": "pompano",
    "hasa hasa": "hasa-hasa",
    "hasahasa": "hasa-hasa",
    "short mackerel": "hasa-hasa",
    "dilis": "dilis",
    "anchovy": "dilis",
    "anchovies": "dilis",
    "espada": "espada",
    "swordfish": "espada",
    "bisugo": "bisugo",
    "threadfin bream": "bisugo",
}


async def _get_role_name(user: dict[str, Any]) -> str:
    role_id = user.get("roleId")
    if not role_id:
        return ""
    role = await get_role(str(role_id))
    return (role.get("name") or "").strip().lower() if role else ""


def _build_species_normalizer(
    species_map: dict[str, str],
) -> Callable[[str], str]:
    """Build a normalizer that maps model class names to canonical DB names."""

    def normalize(name: str) -> str:
        key = name.strip().lower()
        # Check aliases first
        key = _SPECIES_ALIASES.get(key, key)
        # Then check DB species map
        return species_map.get(key, name)

    return normalize


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

        # Validate content type before reading the full payload
        if image.content_type not in _ALLOWED_IMAGE_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Accepted types: {', '.join(sorted(_ALLOWED_IMAGE_CONTENT_TYPES))}",
            )

        # Read and validate image
        try:
            image_bytes = await image.read()
            if not image_bytes:
                logger.error(" image.read() returned empty bytes")
                raise HTTPException(status_code=400, detail="Image file is empty")
            if len(image_bytes) > _MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Image exceeds the maximum allowed size of {_MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB",
                )
        except HTTPException:
            raise
        except Exception as e:
            print(f"ERROR reading image file: {str(e)}")
            raise HTTPException(status_code=400, detail="Failed to read image file")

        image_name = (
            image.filename
            if image.filename
            else f"analysis_{int(datetime.now(timezone.utc).timestamp() * 1000)}.jpg"
        )

        try:
            image_url = save_upload(image_bytes, image_name)
        except Exception as e:
            print(f"ERROR saving image: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to save image")

        # Open and preprocess image for improved model accuracy
        try:
            raw_image = Image.open(BytesIO(image_bytes))
            pil_image = preprocess_image(raw_image)
            width, height = pil_image.size
        except Exception as e:
            print(f"ERROR processing image: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid image format")

        # Get active species (case-insensitive map: lowercase -> canonical name)
        species_map: dict[str, str] = {}
        try:
            species_map = await list_active_species_name_map()
            logger.info(f" Loaded {len(species_map)} active species from DB")
        except Exception as e:
            logger.warning(f" Failed to load active species: {str(e)}")

        _normalize_species = _build_species_normalizer(species_map)

        logger.info(f" Image size={pil_image.size}, mode={pil_image.mode}, bytes={len(image_bytes)}")

        # --- Step 1: Detect fish ---
        try:
            detections = detect_fish(pil_image, confidence=confidence, iou=iou)
            logger.info(f" Detector found {len(detections)} detection(s)")
        except Exception as e:
            print(f"ERROR in fish detection: {str(e)}")
            detections = []

        # --- Step 2: Ensemble verification (classifier verifies each detection) ---
        if detections:
            try:
                detections = verify_detections_with_classifier(pil_image, detections)
                logger.info(f" Ensemble verification completed for {len(detections)} detection(s)")
            except Exception as e:
                logger.warning(f" Ensemble verification failed, using detector results: {str(e)}")

        # Normalize species names from model to match DB names
        for det in detections:
            det["species"] = _normalize_species(det.get("species", "Unknown"))

        # Filter by active species
        if species_map:
            canonical_names = set(species_map.values())
            detections = [
                detection
                for detection in detections
                if detection.get("species") in canonical_names
            ]
            logger.info(f" After filtering by active species: {len(detections)} detection(s)")

        # --- Step 3: Fallback to full-image classifier if no detections ---
        if not detections:
            try:
                species, confidence_score = classify_fish(pil_image, use_tta=True)
                species = _normalize_species(species)
                # Also get top-N for metadata
                top_predictions = classify_fish_top_n(pil_image, n=3, use_tta=True)
                top_predictions = [
                    {**p, "species": _normalize_species(p["species"])}
                    for p in top_predictions
                ]
                logger.info(f" Classifier returned: {species} ({confidence_score:.2f}), top-3: {top_predictions}")
            except Exception as e:
                print(f"ERROR in fish classification: {str(e)}")
                species = "Unknown"
                confidence_score = 0.0
                top_predictions = []

            # If no species detected, create a generic detection for the whole image
            if species == "Unknown" or confidence_score == 0.0:
                logger.warning(" No ML detection/classification. Using fallback: Generic Fish")
                species = "Generic Fish"
                confidence_score = 0.5

            canonical_names = set(species_map.values()) if species_map else set()
            if canonical_names and species not in canonical_names and species != "Generic Fish":
                raise HTTPException(
                    status_code=400,
                    detail="No fish detected in the image.",
                )
            det_entry = {
                "id": "det_0",
                "species": species,
                "confidence": confidence_score,
                "verificationMethod": "classifier_fullimage",
                "boundingBox": {
                    "x": 0.0,
                    "y": 0.0,
                    "width": float(width),
                    "height": float(height),
                },
            }
            if top_predictions:
                det_entry["topPredictions"] = top_predictions
            detections.append(det_entry)

        # --- Step 4: Apply weight/price estimates ---
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

        # singleFish: pick highest confidence, not just first
        if singleFish and detections:
            detections = [max(detections, key=lambda d: d.get("confidence", 0.0))]

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
            logger.info(f" Analysis saved with {len(detections)} detection(s)")
            return result
        except Exception as e:
            print(f"ERROR saving analysis: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to save analysis results")

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception:
        # Catch any unexpected errors — log full traceback server-side,
        # never expose internal details to the client.
        import logging
        logging.getLogger(__name__).exception("Unexpected error in analyze_fish")
        raise HTTPException(status_code=500, detail="Image analysis failed")


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
        species, conf = classify_fish(test_img, use_tta=False)
        result["testPrediction"]["classifier"] = {
            "status": "ok",
            "species": species,
            "confidence": conf,
        }
    except Exception as e:
        result["testPrediction"]["classifier"] = {"status": "error", "error": str(e)}

    result["enhancements"] = {
        "preprocessing": True,
        "testTimeAugmentation": True,
        "ensembleVerification": True,
        "topNPredictions": True,
    }

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
