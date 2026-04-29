"""Seed fish species, pre-trained model registry, and mark as active/approved."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.db import get_db

# Fish species detected/classified by the current models.
# classIndex values match the classifier model's class indices (alpha order
# of the scientific names — this is what the YOLO classifier emits).
# weightRange: typical weight in kg [min, max]
# pricePerKg: typical Philippine market price in PHP [min, max]
# peakMonths: months (1-12) when species is most abundant in PH waters
# habitat: "marine", "freshwater", or "brackish"
#
# Keep this list aligned with `scripts/seed_5_species_only.py` and with the
# alphabetical order of the dataset/<species> folders used to train the
# classifier. The YOLO model's class indices are derived from that order.
DEFAULT_SPECIES: list[dict] = [
    {"name": "Auxis rochei", "classIndex": 0, "scientificName": "Auxis rochei", "genus": "Auxis", "family": "Scombridae", "englishName": "Bullet tuna", "localName": "Mangko/Pirit",
     "weightRange": [0.05, 2.0], "pricePerKg": [80, 150], "peakMonths": [1, 2, 3, 4, 5, 10, 11, 12], "habitat": "marine"},
    {"name": "Elagatis bipinnulata", "classIndex": 1, "scientificName": "Elagatis bipinnulata", "genus": "Elagatis", "family": "Carangidae", "englishName": "Rainbow runner", "localName": "Salindatu/Salmon",
     "weightRange": [0.5, 15.0], "pricePerKg": [150, 300], "peakMonths": [3, 4, 5, 6, 10, 11, 12], "habitat": "marine"},
    {"name": "Euthynnus affinis", "classIndex": 2, "scientificName": "Euthynnus affinis", "genus": "Euthynnus", "family": "Scombridae", "englishName": "Eastern little tuna", "localName": "Patikan/Tulingan",
     "weightRange": [0.5, 5.0], "pricePerKg": [100, 200], "peakMonths": [2, 3, 4, 5, 10, 11, 12], "habitat": "marine"},
    {"name": "Katsuwonus pelamis", "classIndex": 3, "scientificName": "Katsuwonus pelamis", "genus": "Katsuwonus", "family": "Scombridae", "englishName": "Skipjack tuna", "localName": "Sambagon/Tulingan/Bulis",
     "weightRange": [0.75, 15.0], "pricePerKg": [80, 180], "peakMonths": [3, 4, 5, 10, 11, 12], "habitat": "marine"},
    {"name": "Thunnus albacares", "classIndex": 4, "scientificName": "Thunnus albacares", "genus": "Thunnus", "family": "Scombridae", "englishName": "Yellowfin tuna", "localName": "Barilis/Bariles/Karaw",
     "weightRange": [1.0, 80.0], "pricePerKg": [250, 500], "peakMonths": [3, 4, 5, 10, 11, 12], "habitat": "marine"},
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
    from pymongo import UpdateOne

    db = get_db()
    now = datetime.now(timezone.utc)
    extra_fields = (
        "scientificName", "genus", "family", "englishName", "localName",
        "weightRange", "pricePerKg", "peakMonths", "habitat",
    )
    ops = []
    for sp in DEFAULT_SPECIES:
        update_fields: dict = {
            "classIndex": sp["classIndex"],
            "isActive": True,
            "updatedAt": now,
        }
        for field in extra_fields:
            if field in sp:
                update_fields[field] = sp[field]
        ops.append(
            UpdateOne(
                {"name": sp["name"]},
                {
                    "$set": update_fields,
                    "$setOnInsert": {"name": sp["name"], "createdAt": now},
                },
                upsert=True,
            )
        )
    result = await db["fish_species"].bulk_write(ops, ordered=False)
    created = result.upserted_count
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
