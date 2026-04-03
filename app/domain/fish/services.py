from __future__ import annotations

from datetime import datetime, timezone
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


def _clamp_weight(weight: float, species_info: dict[str, Any] | None) -> float:
    """Clamp estimated weight to species-specific range if available.

    This catches wildly wrong ML predictions (e.g., 50kg tilapia).
    """
    if not species_info:
        return weight
    weight_range = species_info.get("weightRange")
    if not weight_range or len(weight_range) < 2:
        return weight
    min_w, max_w = weight_range[0], weight_range[1]
    if weight < min_w * 0.5:
        return min_w
    if weight > max_w * 1.5:
        return max_w
    return weight


def _estimate_price_from_reference(
    weight: float,
    species_info: dict[str, Any] | None,
) -> float | None:
    """Estimate price using species reference data as fallback.

    Returns None if no reference data available.
    """
    if not species_info:
        return None
    price_range = species_info.get("pricePerKg")
    if not price_range or len(price_range) < 2:
        return None
    peak_months = species_info.get("peakMonths") or list(range(1, 13))
    current_month = datetime.now(timezone.utc).month
    is_peak = current_month in peak_months
    avg_price = (price_range[0] + price_range[1]) / 2
    if not is_peak:
        avg_price *= 1.3  # off-season markup
    return avg_price * weight


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

        # Get species reference data for clamping and enrichment
        species_info = None
        if get_species_info:
            species_info = await get_species_info(species)

        # Clamp weight to species-specific range
        estimated_weight = _clamp_weight(estimated_weight, species_info)

        size_category = classify_size(estimated_weight)
        entry = {
            **detection,
            "estimatedWeight": round(estimated_weight, 3),
            "sizeCategory": size_category,
            "lengthCm": length_cm,
            "widthCm": width_cm,
            "pixelLength": pixel_length,
            "keypoints": {
                "mouth": mouth,
                "tail": tail,
            },
        }

        # Enrich with species names and reference data
        if species_info:
            entry["scientificName"] = species_info.get("scientificName")
            entry["genus"] = species_info.get("genus")
            entry["family"] = species_info.get("family")
            entry["englishName"] = species_info.get("englishName")
            entry["localName"] = species_info.get("localName")
            # Include reference data for frontend display
            weight_range = species_info.get("weightRange")
            price_per_kg = species_info.get("pricePerKg")
            if weight_range:
                entry["weightRange"] = {"minKg": weight_range[0], "maxKg": weight_range[1]}
            if price_per_kg:
                peak_months = species_info.get("peakMonths") or list(range(1, 13))
                current_month = datetime.now(timezone.utc).month
                is_peak = current_month in peak_months
                factor = 1.0 if is_peak else 1.3
                entry["estimatedPricePerKg"] = {
                    "minPhp": round(price_per_kg[0] * factor),
                    "maxPhp": round(price_per_kg[1] * factor),
                    "inSeason": is_peak,
                }
            if species_info.get("habitat"):
                entry["habitat"] = species_info["habitat"]

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
    company_id: str | None = None,
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
        "companyId": company_id,
        "createdAt": datetime.now(timezone.utc),
        "detections": detections,
        "totalEstimatedWeight": round(total_weight, 3),
        "predictedPrice": round(total_price, 2),
        "speciesCount": species_count,
        "analyzedAt": datetime.now(timezone.utc).isoformat(),
        "singleFish": single_fish,
        "scaleReferenceCm": scale_reference_cm,
        "imageWidth": image_width,
        "imageHeight": image_height,
        "scannedBy": scanned_by,
        "caughtBy": caught_by,
        "caughtByName": caught_by_name,
    }
