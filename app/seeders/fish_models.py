"""Seed fish species, pre-trained model registry, and mark as active/approved."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.db import get_db

# Fish species detected/classified by the current models
DEFAULT_SPECIES: list[dict] = [
    {"name": "Tuna", "classIndex": 0},
]

# Pre-trained models that ship with the project
DEFAULT_MODELS: list[dict] = [
    {
        "modelType": "detector",
        "version": "1.0.0",
        "description": "YOLOv8 fish detector – pre-trained",
        "relativePath": "models/detector/best.pt",
    },
    {
        "modelType": "classifier",
        "version": "1.0.0",
        "description": "YOLOv8 fish classifier – pre-trained",
        "relativePath": "models/classifier/best.pt",
    },
    {
        "modelType": "weight",
        "version": "1.0.0",
        "description": "Scikit-learn weight estimation – pre-trained",
        "relativePath": "models/weight/weight_model.joblib",
    },
    {
        "modelType": "price",
        "version": "1.0.0",
        "description": "Scikit-learn price prediction – pre-trained",
        "relativePath": "models/price/price_model.joblib",
    },
]


async def seed_fish_species() -> int:
    """Upsert default fish species. Returns number of new species created."""
    db = get_db()
    created = 0
    now = datetime.now(timezone.utc)
    for sp in DEFAULT_SPECIES:
        existing = await db["fish_species"].find_one({"name": sp["name"]})
        if existing:
            # Ensure classIndex is up-to-date
            await db["fish_species"].update_one(
                {"_id": existing["_id"]},
                {"$set": {"classIndex": sp["classIndex"], "isActive": True, "updatedAt": now}},
            )
        else:
            await db["fish_species"].insert_one(
                {
                    "name": sp["name"],
                    "classIndex": sp["classIndex"],
                    "isActive": True,
                    "createdAt": now,
                    "updatedAt": now,
                }
            )
            created += 1
    print(f"  Fish species: {created} created, {len(DEFAULT_SPECIES) - created} updated.")
    return created


async def seed_fish_models() -> int:
    """Register pre-trained models as active and approved. Returns new count."""
    db = get_db()
    settings = get_settings()
    base_dir = Path(settings.model_root).resolve().parent  # project root
    created = 0
    now = datetime.now(timezone.utc)

    for model in DEFAULT_MODELS:
        model_type = model["modelType"]
        version = model["version"]

        # Check if this model version is already registered
        existing = await db["fish_models"].find_one(
            {"modelType": model_type, "version": version}
        )
        if existing:
            # Ensure it's active and approved
            await db["fish_models"].update_one(
                {"_id": existing["_id"]},
                {"$set": {"isActive": True, "status": "approved", "updatedAt": now}},
            )
            continue

        # Deactivate any other models of this type
        await db["fish_models"].update_many(
            {"modelType": model_type}, {"$set": {"isActive": False}}
        )

        # Resolve path – store absolute so inference can find it
        model_path = str((base_dir / model["relativePath"]).resolve())

        await db["fish_models"].insert_one(
            {
                "modelType": model_type,
                "version": version,
                "modelPath": model_path,
                "description": model["description"],
                "isActive": True,
                "status": "approved",
                "createdAt": now,
                "updatedAt": now,
            }
        )
        created += 1

    print(f"  Fish models: {created} registered, {len(DEFAULT_MODELS) - created} already existed.")
    return created
