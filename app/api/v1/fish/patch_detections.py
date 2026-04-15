from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import require_permissions
from app.domain.fish.bulk import build_bulk_summary
from app.infrastructure.fish.repository import (
    get_analysis,
    get_species_index,
    get_species_info,
    update_analysis,
)
from app.infrastructure.fish.estimator import estimate_price, estimate_weight

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fish/analyses", tags=["fish"])


class DetectionAdd(BaseModel):
    species: str
    estimatedWeight: float | None = None
    confidence: float | None = 1.0
    boundingBox: dict[str, float]


class DetectionUpdate(BaseModel):
    id: str
    species: str | None = None


class PatchDetections(BaseModel):
    add: list[DetectionAdd] = []
    remove: list[str] = []
    update: list[DetectionUpdate] = []


@router.patch("/{analysis_id}/detections")
async def patch_detections(
    analysis_id: str,
    patch: PatchDetections,
    user: dict[str, Any] = Depends(require_permissions("fish:analyze")),
):
    analysis = await get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    detections: list[dict[str, Any]] = list(analysis.get("detections") or [])

    if patch.remove:
        remove_ids = set(patch.remove)
        detections = [d for d in detections if d.get("id") not in remove_ids]

    if patch.update:
        by_id = {d.get("id"): d for d in detections}
        for upd in patch.update:
            det = by_id.get(upd.id)
            if det is None:
                continue
            if upd.species is not None:
                det["species"] = upd.species
                species_idx = await get_species_index(upd.species)
                weight = float(det.get("estimatedWeight") or 0.0)
                det["predictedPrice"] = estimate_price(species_idx, weight)

    for add in patch.add:
        new_id = f"det_{uuid.uuid4().hex[:8]}"
        species_idx = await get_species_index(add.species)
        bbox = add.boundingBox
        weight = add.estimatedWeight
        if weight is None:
            weight = estimate_weight(
                species_idx, float(bbox.get("width") or 0),
                float(bbox.get("height") or 0),
                None, None, None,
            )
        det = {
            "id": new_id,
            "species": add.species,
            "confidence": add.confidence or 1.0,
            "boundingBox": bbox,
            "estimatedWeight": float(weight),
            "verificationMethod": "manual_edit",
        }
        info = await get_species_info(add.species)
        if info:
            det["scientificName"] = info.get("scientificName")
            det["englishName"] = info.get("englishName")
            det["localName"] = info.get("localName")
        detections.append(det)

    total_weight = round(sum(float(d.get("estimatedWeight") or 0.0) for d in detections), 3)
    total_price = 0.0
    species_count: dict[str, int] = {}
    for d in detections:
        s = d.get("species") or "Unknown"
        species_count[s] = species_count.get(s, 0) + 1
        idx = await get_species_index(s)
        total_price += estimate_price(idx, float(d.get("estimatedWeight") or 0.0))

    update_doc: dict[str, Any] = {
        "detections": detections,
        "totalEstimatedWeight": total_weight,
        "predictedPrice": round(total_price, 2),
        "speciesCount": species_count,
    }
    if (analysis.get("mode") or "single") == "bulk":
        update_doc["bulkSummary"] = build_bulk_summary(detections)

    updated = await update_analysis(analysis_id, update_doc)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update analysis")
    return updated
