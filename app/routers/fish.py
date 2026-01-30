from datetime import datetime
from typing import Any
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image
import numpy as np
import joblib

from app.core.config import get_settings

from app.db import get_db
from app.deps import get_current_user
from app.utils import serialize_doc


router = APIRouter(prefix="/fish", tags=["fish"])
_classifier_model = None
_weight_model = None
_price_model = None
_detector_model = None


def _load_classifier():
    global _classifier_model
    if _classifier_model is not None:
        return _classifier_model
    settings = get_settings()
    if not settings.classifier_model_path:
        return None
    try:
        from ultralytics import YOLO

        _classifier_model = YOLO(settings.classifier_model_path)
        return _classifier_model
    except Exception:
        return None


def _load_weight_model():
    global _weight_model
    if _weight_model is not None:
        return _weight_model
    settings = get_settings()
    if not settings.weight_model_path:
        return None
    try:
        _weight_model = joblib.load(settings.weight_model_path)
        return _weight_model
    except Exception:
        return None


def _load_price_model():
    global _price_model
    if _price_model is not None:
        return _price_model
    settings = get_settings()
    if not settings.price_model_path:
        return None
    try:
        _price_model = joblib.load(settings.price_model_path)
        return _price_model
    except Exception:
        return None


def _load_detector():
    global _detector_model
    if _detector_model is not None:
        return _detector_model
    settings = get_settings()
    if not settings.detector_model_path:
        return None
    try:
        from ultralytics import YOLO

        _detector_model = YOLO(settings.detector_model_path)
        return _detector_model
    except Exception:
        return None


async def _get_species_index(species: str | None) -> int:
    if not species:
        return 0
    db = get_db()
    record = await db["fish_species"].find_one({"name": species})
    if record and record.get("classIndex") is not None:
        return int(record.get("classIndex"))
    return 0


def _estimate_cm_from_scale(
    width: int,
    height: int,
    scale_reference_cm: float | None,
) -> tuple[float | None, float | None]:
    if not scale_reference_cm or scale_reference_cm <= 0:
        return None, None
    longest = max(width, height)
    shortest = min(width, height)
    pixels_per_cm = longest / scale_reference_cm
    if pixels_per_cm <= 0:
        return None, None
    length_cm = longest / pixels_per_cm
    width_cm = shortest / pixels_per_cm
    return length_cm, width_cm


def _estimate_weight(
    species_index: int,
    width: float,
    height: float,
    scale_reference_cm: float | None,
    length_cm: float | None,
    width_cm: float | None,
) -> float:
    weight_model = _load_weight_model()
    if weight_model is not None:
        features = np.array(
            [
                [
                    species_index,
                    float(width),
                    float(height),
                    float(scale_reference_cm or 0),
                    float(length_cm or 0),
                    float(width_cm or 0),
                ]
            ],
            dtype=float,
        )
        try:
            return float(weight_model.predict(features)[0])
        except Exception:
            pass
    return float(width * height) * 0.000001


def _estimate_price(species_index: int, estimated_weight: float) -> float:
    price_model = _load_price_model()
    if price_model is not None:
        try:
            price_per_kg = float(
                price_model.predict(
                    np.array([[species_index, estimated_weight]], dtype=float)
                )[0]
            )
            return price_per_kg * estimated_weight
        except Exception:
            pass
    return estimated_weight * 8.5


def _save_upload(image_bytes: bytes, file_name: str) -> str:
    settings = get_settings()
    root = Path(settings.upload_root) / "fish"
    root.mkdir(parents=True, exist_ok=True)
    target = root / file_name
    target.write_bytes(image_bytes)
    return f"/uploads/fish/{file_name}"


@router.post("/analyze")
async def analyze_fish(
    image: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
    singleFish: bool | None = None,
    scaleReferenceCm: float | None = None,
    confidence: float | None = None,
    iou: float | None = None,
):
    if not image:
        raise HTTPException(status_code=400, detail="Image file is required")
    image_bytes = image.file.read()
    image_name = (
        image.filename
        if image.filename
        else f"analysis_{int(datetime.utcnow().timestamp() * 1000)}.jpg"
    )
    image_url = _save_upload(image_bytes, image_name)
    pil_image = Image.open(BytesIO(image_bytes)).convert("RGB")
    width, height = pil_image.size

    detections: list[dict[str, Any]] = []
    detector = _load_detector()
    if detector is not None:
        try:
            settings = get_settings()
            results = detector.predict(
                pil_image,
                verbose=False,
                conf=confidence if confidence is not None else settings.detector_confidence,
                iou=iou if iou is not None else settings.detector_iou,
            )
            if results:
                result = results[0]
                names = result.names if hasattr(result, "names") else {}
                for idx, box in enumerate(result.boxes):
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    confidence = float(box.conf[0]) if box.conf is not None else 0.0
                    cls_idx = int(box.cls[0]) if box.cls is not None else 0
                    species = names.get(cls_idx, "Unknown")
                    bbox_width = max(0.0, x2 - x1)
                    bbox_height = max(0.0, y2 - y1)

                    species_index = await _get_species_index(species)
                    length_cm, width_cm = _estimate_cm_from_scale(
                        int(bbox_width), int(bbox_height), scaleReferenceCm
                    )
                    estimated_weight = _estimate_weight(
                        species_index,
                        bbox_width,
                        bbox_height,
                        scaleReferenceCm,
                        length_cm,
                        width_cm,
                    )
                    estimated_price = _estimate_price(species_index, estimated_weight)

                    detections.append(
                        {
                            "id": f"det_{idx}",
                            "species": species,
                            "confidence": confidence,
                            "boundingBox": {
                                "x": float(x1),
                                "y": float(y1),
                                "width": float(bbox_width),
                                "height": float(bbox_height),
                            },
                            "estimatedWeight": estimated_weight,
                        }
                    )
        except Exception:
            detections = []

    if not detections:
        classifier = _load_classifier()
        species = "Unknown"
        confidence = 0.0
        if classifier is not None:
            try:
                results = classifier.predict(pil_image, verbose=False)
                if results:
                    result = results[0]
                    if hasattr(result, "names") and hasattr(result, "probs"):
                        top_idx = int(result.probs.top1)
                        species = result.names.get(top_idx, "Unknown")
                        confidence = float(result.probs.top1conf)
            except Exception:
                species = "Unknown"
                confidence = 0.0

        species_index = await _get_species_index(species)
        length_cm, width_cm = _estimate_cm_from_scale(
            width, height, scaleReferenceCm
        )
        estimated_weight = _estimate_weight(
            species_index,
            float(width),
            float(height),
            scaleReferenceCm,
            length_cm,
            width_cm,
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
                "estimatedWeight": estimated_weight,
            }
        )

    if singleFish and detections:
        detections = [detections[0]]

    species_count: dict[str, int] = {}
    total_weight = 0.0
    total_price = 0.0
    for detection in detections:
        species_name = detection.get("species") or "Unknown"
        species_count[species_name] = species_count.get(species_name, 0) + 1
        weight = float(detection.get("estimatedWeight") or 0.0)
        total_weight += weight
        species_index = await _get_species_index(species_name)
        total_price += _estimate_price(species_index, weight)

    analysis = {
        "imageUrl": image_url,
        "userId": user["id"],
        "createdAt": datetime.utcnow(),
        "detections": detections,
        "totalEstimatedWeight": total_weight,
        "predictedPrice": total_price,
        "speciesCount": species_count,
        "analyzedAt": datetime.utcnow().isoformat(),
        "singleFish": singleFish,
        "scaleReferenceCm": scaleReferenceCm,
    }
    db = get_db()
    result = await db["fish_analyses"].insert_one(analysis)
    stored = await db["fish_analyses"].find_one({"_id": result.inserted_id})
    return serialize_doc(stored)


@router.get("/analytics")
async def analytics(user: dict[str, Any] = Depends(get_current_user)):
    db = get_db()
    total = await db["fish_analyses"].count_documents({})
    mine = await db["fish_analyses"].count_documents({"userId": user["id"]})
    return {"totalAnalyses": total, "userAnalyses": mine}


@router.get("/analysis-history")
async def analysis_history(user: dict[str, Any] = Depends(get_current_user)):
    db = get_db()
    cursor = db["fish_analyses"].find({"userId": user["id"]}).sort("createdAt", -1)
    results = [serialize_doc(doc) async for doc in cursor]
    return results
