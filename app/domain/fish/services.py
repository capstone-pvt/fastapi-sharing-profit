from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable


def estimate_cm_from_scale(
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


def classify_size_by_weight(
    weight_kg: float, *, small_max_kg: float, medium_max_kg: float
) -> str:
    if weight_kg <= small_max_kg:
        return "Small"
    if weight_kg <= medium_max_kg:
        return "Medium"
    return "Large"


async def apply_estimates_to_detections(
    detections: list[dict[str, Any]],
    *,
    scale_reference_cm: float | None,
    get_species_index: Callable[[str | None], Awaitable[int]],
    get_species_info: Callable[[str | None], Awaitable[dict[str, Any] | None]] | None = None,
    estimate_weight: Callable[
        [int, float, float, float | None, float | None, float | None], float
    ],
    estimate_price: Callable[[int, float], float],
    classify_size: Callable[[float], str],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for detection in detections:
        bbox = detection.get("boundingBox") or {}
        bbox_width = float(bbox.get("width") or 0.0)
        bbox_height = float(bbox.get("height") or 0.0)
        bbox_x = float(bbox.get("x") or 0.0)
        bbox_y = float(bbox.get("y") or 0.0)
        species = detection.get("species")
        species_index = await get_species_index(species)
        length_cm, width_cm = estimate_cm_from_scale(
            int(bbox_width), int(bbox_height), scale_reference_cm
        )
        if bbox_width >= bbox_height:
            mouth = {"x": bbox_x, "y": bbox_y + (bbox_height / 2)}
            tail = {"x": bbox_x + bbox_width, "y": bbox_y + (bbox_height / 2)}
            pixel_length = bbox_width
        else:
            mouth = {"x": bbox_x + (bbox_width / 2), "y": bbox_y}
            tail = {"x": bbox_x + (bbox_width / 2), "y": bbox_y + bbox_height}
            pixel_length = bbox_height
        estimated_weight = estimate_weight(
            species_index,
            bbox_width,
            bbox_height,
            scale_reference_cm,
            length_cm,
            width_cm,
        )
        size_category = classify_size(estimated_weight)
        entry = {
            **detection,
            "estimatedWeight": estimated_weight,
            "sizeCategory": size_category,
            "lengthCm": length_cm,
            "widthCm": width_cm,
            "pixelLength": pixel_length,
            "keypoints": {
                "mouth": mouth,
                "tail": tail,
            },
        }
        # Enrich with species names (scientific, english, local)
        if get_species_info:
            info = await get_species_info(species)
            if info:
                entry["scientificName"] = info.get("scientificName")
                entry["englishName"] = info.get("englishName")
                entry["localName"] = info.get("localName")
        enriched.append(entry)
    return enriched


async def build_analysis(
    detections: list[dict[str, Any]],
    *,
    user_id: str,
    image_url: str,
    scale_reference_cm: float | None,
    single_fish: bool | None,
    image_width: int | None = None,
    image_height: int | None = None,
    scanned_by: str | None = None,
    caught_by: str | None = None,
    caught_by_name: str | None = None,
    get_species_index: Callable[[str | None], Awaitable[int]],
    estimate_price: Callable[[int, float], float],
) -> dict[str, Any]:
    species_count: dict[str, int] = {}
    total_weight = 0.0
    total_price = 0.0
    for detection in detections:
        species_name = detection.get("species") or "Unknown"
        species_count[species_name] = species_count.get(species_name, 0) + 1
        weight = float(detection.get("estimatedWeight") or 0.0)
        total_weight += weight
        species_index = await get_species_index(species_name)
        total_price += estimate_price(species_index, weight)

    return {
        "imageUrl": image_url,
        "userId": user_id,
        "createdAt": datetime.utcnow(),
        "detections": detections,
        "totalEstimatedWeight": total_weight,
        "predictedPrice": total_price,
        "speciesCount": species_count,
        "analyzedAt": datetime.utcnow().isoformat(),
        "singleFish": single_fish,
        "scaleReferenceCm": scale_reference_cm,
        "imageWidth": image_width,
        "imageHeight": image_height,
        "scannedBy": scanned_by,
        "caughtBy": caught_by,
        "caughtByName": caught_by_name,
    }
