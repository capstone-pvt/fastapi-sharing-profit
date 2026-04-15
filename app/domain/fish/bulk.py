from __future__ import annotations

from collections import Counter
from typing import Any


_LOW_CONFIDENCE_THRESHOLD = 0.30


def build_bulk_summary(detections: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the bulkSummary block from a list of enriched detection dicts."""
    if not detections:
        return {
            "totalFish": 0,
            "dominantSpecies": None,
            "breakdown": [],
            "estimatedTotalKg": 0.0,
            "estimatedTotalPhp": 0.0,
            "warnings": [],
        }

    total_fish = len(detections)
    species_counter: Counter[str] = Counter()
    species_kg: dict[str, float] = {}
    total_php = 0.0

    for det in detections:
        species = det.get("species") or "Unknown"
        weight = float(det.get("estimatedWeight") or 0.0)
        species_counter[species] += 1
        species_kg[species] = species_kg.get(species, 0.0) + weight

        price_block = det.get("estimatedPricePerKg") or {}
        min_php = float(price_block.get("minPhp") or 0.0)
        max_php = float(price_block.get("maxPhp") or 0.0)
        avg_per_kg = (min_php + max_php) / 2.0 if (min_php or max_php) else 0.0
        total_php += avg_per_kg * weight

    breakdown = []
    for species, count in sorted(
        species_counter.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        total_kg = round(species_kg[species], 3)
        avg_kg = round(total_kg / count, 3) if count else 0.0
        breakdown.append({
            "species": species,
            "count": count,
            "totalKg": total_kg,
            "avgKg": avg_kg,
        })

    dominant = breakdown[0]["species"] if breakdown else None
    total_kg = round(sum(species_kg.values()), 3)

    warnings: list[str] = []
    low_conf = sum(
        1 for d in detections
        if float(d.get("confidence") or 1.0) < _LOW_CONFIDENCE_THRESHOLD
    )
    if low_conf:
        warnings.append(
            f"{low_conf} detections below confidence threshold — review"
        )

    return {
        "totalFish": total_fish,
        "dominantSpecies": dominant,
        "breakdown": breakdown,
        "estimatedTotalKg": total_kg,
        "estimatedTotalPhp": round(total_php, 2),
        "warnings": warnings,
    }
