"""Seed fish species, pre-trained model registry, and mark as active/approved."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.db import get_db

# Fish species detected/classified by the current models.
# classIndex values match the classifier model's class indices.
DEFAULT_SPECIES: list[dict] = [
    {"name": "Bangus", "classIndex": 0, "scientificName": "Chanos chanos", "englishName": "Milkfish", "localName": "Bangus"},
    {"name": "Big Head Carp", "classIndex": 1, "scientificName": "Hypophthalmichthys nobilis", "englishName": "Big Head Carp", "localName": "Big Head Carp"},
    {"name": "Black Sea Sprat", "classIndex": 2, "scientificName": "Clupeonella cultriventris", "englishName": "Black Sea Sprat", "localName": "Black Sea Sprat"},
    {"name": "Black Spotted Barb", "classIndex": 3, "scientificName": "Dawkinsia filamentosa", "englishName": "Black Spotted Barb", "localName": "Black Spotted Barb"},
    {"name": "Catfish", "classIndex": 4, "scientificName": "Clarias batrachus", "englishName": "Catfish", "localName": "Hito"},
    {"name": "Climbing Perch", "classIndex": 5, "scientificName": "Anabas testudineus", "englishName": "Climbing Perch", "localName": "Martiniko"},
    {"name": "Fourfinger Threadfin", "classIndex": 6, "scientificName": "Eleutheronema tetradactylum", "englishName": "Fourfinger Threadfin", "localName": "Mamali"},
    {"name": "Freshwater Eel", "classIndex": 7, "scientificName": "Anguilla marmorata", "englishName": "Freshwater Eel", "localName": "Igat"},
    {"name": "Gilt-Head Bream", "classIndex": 8, "scientificName": "Sparus aurata", "englishName": "Gilt-Head Bream", "localName": "Gilt-Head Bream"},
    {"name": "Glass Perchlet", "classIndex": 9, "scientificName": "Ambassis urotaenia", "englishName": "Glass Perchlet", "localName": "Glass Perchlet"},
    {"name": "Goby", "classIndex": 10, "scientificName": "Glossogobius giuris", "englishName": "Goby", "localName": "Biya"},
    {"name": "Gold Fish", "classIndex": 11, "scientificName": "Carassius auratus", "englishName": "Gold Fish", "localName": "Gold Fish"},
    {"name": "Gourami", "classIndex": 12, "scientificName": "Osphronemus goramy", "englishName": "Gourami", "localName": "Gurami"},
    {"name": "Grass Carp", "classIndex": 13, "scientificName": "Ctenopharyngodon idella", "englishName": "Grass Carp", "localName": "Grass Carp"},
    {"name": "Green Spotted Puffer", "classIndex": 14, "scientificName": "Tetraodon nigroviridis", "englishName": "Green Spotted Puffer", "localName": "Butete"},
    {"name": "Hourse Mackerel", "classIndex": 15, "scientificName": "Trachurus trachurus", "englishName": "Horse Mackerel", "localName": "Galunggong"},
    {"name": "Indian Carp", "classIndex": 16, "scientificName": "Catla catla", "englishName": "Indian Carp", "localName": "Indian Carp"},
    {"name": "Indo-Pacific Tarpon", "classIndex": 17, "scientificName": "Megalops cyprinoides", "englishName": "Indo-Pacific Tarpon", "localName": "Buan-buan"},
    {"name": "Jaguar Gapote", "classIndex": 18, "scientificName": "Parachromis managuensis", "englishName": "Jaguar Gapote", "localName": "Jaguar Gapote"},
    {"name": "Janitor Fish", "classIndex": 19, "scientificName": "Pterygoplichthys disjunctivus", "englishName": "Janitor Fish", "localName": "Janitor Fish"},
    {"name": "Knifefish", "classIndex": 20, "scientificName": "Chitala ornata", "englishName": "Knifefish", "localName": "Knifefish"},
    {"name": "Long-Snouted Pipefish", "classIndex": 21, "scientificName": "Syngnathus temminckii", "englishName": "Long-Snouted Pipefish", "localName": "Long-Snouted Pipefish"},
    {"name": "Mosquito Fish", "classIndex": 22, "scientificName": "Gambusia affinis", "englishName": "Mosquito Fish", "localName": "Mosquito Fish"},
    {"name": "Mudfish", "classIndex": 23, "scientificName": "Channa striata", "englishName": "Mudfish", "localName": "Dalag"},
    {"name": "Mullet", "classIndex": 24, "scientificName": "Mugil cephalus", "englishName": "Mullet", "localName": "Banak"},
    {"name": "Pangasius", "classIndex": 25, "scientificName": "Pangasianodon hypophthalmus", "englishName": "Pangasius", "localName": "Pangasius"},
    {"name": "Perch", "classIndex": 26, "scientificName": "Perca fluviatilis", "englishName": "Perch", "localName": "Perch"},
    {"name": "Red Mullet", "classIndex": 27, "scientificName": "Mullus barbatus", "englishName": "Red Mullet", "localName": "Red Mullet"},
    {"name": "Red Sea Bream", "classIndex": 28, "scientificName": "Pagrus major", "englishName": "Red Sea Bream", "localName": "Red Sea Bream"},
    {"name": "Scat Fish", "classIndex": 29, "scientificName": "Scatophagus argus", "englishName": "Scat Fish", "localName": "Kitang"},
    {"name": "Sea Bass", "classIndex": 30, "scientificName": "Lates calcarifer", "englishName": "Sea Bass", "localName": "Apahap"},
    {"name": "Shrimp", "classIndex": 31, "scientificName": "Penaeus monodon", "englishName": "Shrimp", "localName": "Hipon / Sugpo"},
    {"name": "Silver Barb", "classIndex": 32, "scientificName": "Barbonymus gonionotus", "englishName": "Silver Barb", "localName": "Silver Barb"},
    {"name": "Silver Carp", "classIndex": 33, "scientificName": "Hypophthalmichthys molitrix", "englishName": "Silver Carp", "localName": "Silver Carp"},
    {"name": "Silver Perch", "classIndex": 34, "scientificName": "Leiopotherapon plumbeus", "englishName": "Silver Perch", "localName": "Ayungin"},
    {"name": "Snakehead", "classIndex": 35, "scientificName": "Channa striata", "englishName": "Snakehead", "localName": "Dalag"},
    {"name": "Striped Red Mullet", "classIndex": 36, "scientificName": "Mullus surmuletus", "englishName": "Striped Red Mullet", "localName": "Striped Red Mullet"},
    {"name": "Tenpounder", "classIndex": 37, "scientificName": "Elops machnata", "englishName": "Tenpounder", "localName": "Bidbid"},
    {"name": "Tilapia", "classIndex": 38, "scientificName": "Oreochromis niloticus", "englishName": "Tilapia", "localName": "Tilapia"},
    {"name": "Trout", "classIndex": 39, "scientificName": "Oncorhynchus mykiss", "englishName": "Trout", "localName": "Trout"},
    {"name": "Tuna", "classIndex": 40, "scientificName": "Thunnus albacares", "englishName": "Yellowfin Tuna", "localName": "Barilis / Tambakol"},
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
            # Ensure classIndex and species names are up-to-date
            update_fields: dict = {
                "classIndex": sp["classIndex"],
                "isActive": True,
                "updatedAt": now,
            }
            for field in ("scientificName", "englishName", "localName"):
                if field in sp:
                    update_fields[field] = sp[field]
            await db["fish_species"].update_one(
                {"_id": existing["_id"]},
                {"$set": update_fields},
            )
        else:
            doc: dict = {
                "name": sp["name"],
                "classIndex": sp["classIndex"],
                "isActive": True,
                "createdAt": now,
                "updatedAt": now,
            }
            for field in ("scientificName", "englishName", "localName"):
                if field in sp:
                    doc[field] = sp[field]
            await db["fish_species"].insert_one(doc)
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
