from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_sample_doc(
    *,
    payload: dict[str, Any],
    user_id: str,
    image_path: str,
    image_url: str,
    trained_by: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = {
        "userId": user_id,
        "imageUrl": image_url,
        "imagePath": image_path,
        "species": payload.get("species"),
        "scientificName": payload.get("scientificName"),
        "englishName": payload.get("englishName"),
        "localName": payload.get("localName"),
        "weightKg": payload.get("weightKg"),
        "pricePerKg": payload.get("pricePerKg"),
        "lengthCm": payload.get("lengthCm"),
        "widthCm": payload.get("widthCm"),
        "heightCm": payload.get("heightCm"),
        "scaleReferenceCm": payload.get("scaleReferenceCm"),
        "notes": payload.get("notes"),
        "bbox": None,
        "capturedAt": payload.get("capturedAt"),
        "createdAt": now,
        "updatedAt": now,
        "trainedBy": trained_by,
        # Correction metadata (non-null when source == "scanner_correction")
        "source": payload.get("source"),
        "originalSpecies": payload.get("originalSpecies"),
        "originalConfidence": payload.get("originalConfidence"),
        "analysisId": payload.get("analysisId"),
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
    return doc


def build_samples_query(
    species: str | None = None,
    source: str | None = None,
    review_status: str | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if species:
        query["species"] = species
    if source:
        query["source"] = source
    if review_status == "pending":
        query["reviewStatus"] = {"$exists": False}
    elif review_status:
        query["reviewStatus"] = review_status
    return query
