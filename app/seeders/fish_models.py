"""Seed fish species, pre-trained model registry, and mark as active/approved."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.db import get_db

# Fish species detected/classified by the current models.
# classIndex values match the classifier model's class indices.
# weightRange: typical weight in kg [min, max]
# pricePerKg: typical Philippine market price in PHP [min, max]
# peakMonths: months (1-12) when species is most abundant in PH waters
# habitat: "marine", "freshwater", or "brackish"
DEFAULT_SPECIES: list[dict] = [
    {"name": "Bangus", "classIndex": 0, "scientificName": "Chanos chanos", "genus": "Chanos", "family": "Chanidae", "englishName": "Milkfish", "localName": "Bangus",
     "weightRange": [0.3, 3.0], "pricePerKg": [140, 220], "peakMonths": [3, 4, 5, 6, 7, 8, 9, 10], "habitat": "brackish"},
    {"name": "Big Head Carp", "classIndex": 1, "scientificName": "Hypophthalmichthys nobilis", "genus": "Hypophthalmichthys", "family": "Cyprinidae", "englishName": "Big Head Carp", "localName": "Big Head Carp",
     "weightRange": [1.0, 15.0], "pricePerKg": [80, 150], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Black Sea Sprat", "classIndex": 2, "scientificName": "Clupeonella cultriventris", "genus": "Clupeonella", "family": "Clupeidae", "englishName": "Black Sea Sprat", "localName": "Black Sea Sprat",
     "weightRange": [0.01, 0.05], "pricePerKg": [60, 120], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    {"name": "Black Spotted Barb", "classIndex": 3, "scientificName": "Dawkinsia filamentosa", "genus": "Dawkinsia", "family": "Cyprinidae", "englishName": "Black Spotted Barb", "localName": "Black Spotted Barb",
     "weightRange": [0.05, 0.3], "pricePerKg": [80, 140], "peakMonths": [6, 7, 8, 9, 10], "habitat": "freshwater"},
    {"name": "Catfish", "classIndex": 4, "scientificName": "Clarias batrachus", "genus": "Clarias", "family": "Clariidae", "englishName": "Catfish", "localName": "Hito",
     "weightRange": [0.2, 2.0], "pricePerKg": [120, 200], "peakMonths": [5, 6, 7, 8, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Climbing Perch", "classIndex": 5, "scientificName": "Anabas testudineus", "genus": "Anabas", "family": "Anabantidae", "englishName": "Climbing Perch", "localName": "Martiniko",
     "weightRange": [0.05, 0.3], "pricePerKg": [100, 180], "peakMonths": [6, 7, 8, 9, 10], "habitat": "freshwater"},
    {"name": "Fourfinger Threadfin", "classIndex": 6, "scientificName": "Eleutheronema tetradactylum", "genus": "Eleutheronema", "family": "Polynemidae", "englishName": "Fourfinger Threadfin", "localName": "Mamali",
     "weightRange": [0.5, 5.0], "pricePerKg": [180, 300], "peakMonths": [3, 4, 5, 9, 10, 11], "habitat": "marine"},
    {"name": "Freshwater Eel", "classIndex": 7, "scientificName": "Anguilla marmorata", "genus": "Anguilla", "family": "Anguillidae", "englishName": "Freshwater Eel", "localName": "Igat",
     "weightRange": [0.3, 3.0], "pricePerKg": [200, 400], "peakMonths": [6, 7, 8, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Gilt-Head Bream", "classIndex": 8, "scientificName": "Sparus aurata", "genus": "Sparus", "family": "Sparidae", "englishName": "Gilt-Head Bream", "localName": "Gilt-Head Bream",
     "weightRange": [0.3, 2.5], "pricePerKg": [250, 450], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    {"name": "Glass Perchlet", "classIndex": 9, "scientificName": "Ambassis urotaenia", "genus": "Ambassis", "family": "Ambassidae", "englishName": "Glass Perchlet", "localName": "Glass Perchlet",
     "weightRange": [0.005, 0.03], "pricePerKg": [60, 100], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Goby", "classIndex": 10, "scientificName": "Glossogobius giuris", "genus": "Glossogobius", "family": "Gobiidae", "englishName": "Goby", "localName": "Biya",
     "weightRange": [0.01, 0.1], "pricePerKg": [100, 200], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Gold Fish", "classIndex": 11, "scientificName": "Carassius auratus", "genus": "Carassius", "family": "Cyprinidae", "englishName": "Gold Fish", "localName": "Gold Fish",
     "weightRange": [0.01, 0.3], "pricePerKg": [50, 100], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Gourami", "classIndex": 12, "scientificName": "Osphronemus goramy", "genus": "Osphronemus", "family": "Osphronemidae", "englishName": "Gourami", "localName": "Gurami",
     "weightRange": [0.3, 4.0], "pricePerKg": [150, 280], "peakMonths": [3, 4, 5, 6, 7, 8, 9, 10], "habitat": "freshwater"},
    {"name": "Grass Carp", "classIndex": 13, "scientificName": "Ctenopharyngodon idella", "genus": "Ctenopharyngodon", "family": "Cyprinidae", "englishName": "Grass Carp", "localName": "Grass Carp",
     "weightRange": [1.0, 15.0], "pricePerKg": [80, 160], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Green Spotted Puffer", "classIndex": 14, "scientificName": "Tetraodon nigroviridis", "genus": "Tetraodon", "family": "Tetraodontidae", "englishName": "Green Spotted Puffer", "localName": "Butete",
     "weightRange": [0.01, 0.1], "pricePerKg": [40, 80], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "brackish"},
    {"name": "Hourse Mackerel", "classIndex": 15, "scientificName": "Trachurus trachurus", "genus": "Trachurus", "family": "Carangidae", "englishName": "Horse Mackerel", "localName": "Galunggong",
     "weightRange": [0.1, 0.5], "pricePerKg": [120, 200], "peakMonths": [10, 11, 12, 1, 2, 3, 4], "habitat": "marine"},
    {"name": "Indian Carp", "classIndex": 16, "scientificName": "Catla catla", "genus": "Catla", "family": "Cyprinidae", "englishName": "Indian Carp", "localName": "Indian Carp",
     "weightRange": [1.0, 10.0], "pricePerKg": [80, 150], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Indo-Pacific Tarpon", "classIndex": 17, "scientificName": "Megalops cyprinoides", "genus": "Megalops", "family": "Megalopidae", "englishName": "Indo-Pacific Tarpon", "localName": "Buan-buan",
     "weightRange": [0.5, 5.0], "pricePerKg": [100, 180], "peakMonths": [3, 4, 5, 6, 7, 8], "habitat": "brackish"},
    {"name": "Jaguar Gapote", "classIndex": 18, "scientificName": "Parachromis managuensis", "genus": "Parachromis", "family": "Cichlidae", "englishName": "Jaguar Gapote", "localName": "Jaguar Gapote",
     "weightRange": [0.3, 2.0], "pricePerKg": [100, 180], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Janitor Fish", "classIndex": 19, "scientificName": "Pterygoplichthys disjunctivus", "genus": "Pterygoplichthys", "family": "Loricariidae", "englishName": "Janitor Fish", "localName": "Janitor Fish",
     "weightRange": [0.1, 1.0], "pricePerKg": [20, 50], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Knifefish", "classIndex": 20, "scientificName": "Chitala ornata", "genus": "Chitala", "family": "Notopteridae", "englishName": "Knifefish", "localName": "Knifefish",
     "weightRange": [0.5, 5.0], "pricePerKg": [120, 220], "peakMonths": [6, 7, 8, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Long-Snouted Pipefish", "classIndex": 21, "scientificName": "Syngnathus temminckii", "genus": "Syngnathus", "family": "Syngnathidae", "englishName": "Long-Snouted Pipefish", "localName": "Long-Snouted Pipefish",
     "weightRange": [0.001, 0.01], "pricePerKg": [30, 60], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "marine"},
    {"name": "Mosquito Fish", "classIndex": 22, "scientificName": "Gambusia affinis", "genus": "Gambusia", "family": "Poeciliidae", "englishName": "Mosquito Fish", "localName": "Mosquito Fish",
     "weightRange": [0.001, 0.005], "pricePerKg": [20, 40], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Mudfish", "classIndex": 23, "scientificName": "Channa striata", "genus": "Channa", "family": "Channidae", "englishName": "Mudfish", "localName": "Dalag",
     "weightRange": [0.3, 3.0], "pricePerKg": [180, 320], "peakMonths": [6, 7, 8, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Mullet", "classIndex": 24, "scientificName": "Mugil cephalus", "genus": "Mugil", "family": "Mugilidae", "englishName": "Mullet", "localName": "Banak",
     "weightRange": [0.2, 2.0], "pricePerKg": [140, 250], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    {"name": "Pangasius", "classIndex": 25, "scientificName": "Pangasianodon hypophthalmus", "genus": "Pangasianodon", "family": "Pangasiidae", "englishName": "Pangasius", "localName": "Pangasius",
     "weightRange": [0.5, 10.0], "pricePerKg": [80, 150], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Perch", "classIndex": 26, "scientificName": "Perca fluviatilis", "genus": "Perca", "family": "Percidae", "englishName": "Perch", "localName": "Perch",
     "weightRange": [0.1, 1.5], "pricePerKg": [150, 280], "peakMonths": [3, 4, 5, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Red Mullet", "classIndex": 27, "scientificName": "Mullus barbatus", "genus": "Mullus", "family": "Mullidae", "englishName": "Red Mullet", "localName": "Red Mullet",
     "weightRange": [0.05, 0.3], "pricePerKg": [200, 350], "peakMonths": [4, 5, 6, 7, 8, 9], "habitat": "marine"},
    {"name": "Red Sea Bream", "classIndex": 28, "scientificName": "Pagrus major", "genus": "Pagrus", "family": "Sparidae", "englishName": "Red Sea Bream", "localName": "Red Sea Bream",
     "weightRange": [0.3, 4.0], "pricePerKg": [280, 500], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    {"name": "Scat Fish", "classIndex": 29, "scientificName": "Scatophagus argus", "genus": "Scatophagus", "family": "Scatophagidae", "englishName": "Scat Fish", "localName": "Kitang",
     "weightRange": [0.1, 0.5], "pricePerKg": [100, 180], "peakMonths": [3, 4, 5, 6, 7, 8, 9, 10], "habitat": "brackish"},
    {"name": "Sea Bass", "classIndex": 30, "scientificName": "Lates calcarifer", "genus": "Lates", "family": "Latidae", "englishName": "Sea Bass", "localName": "Apahap",
     "weightRange": [0.5, 10.0], "pricePerKg": [280, 500], "peakMonths": [3, 4, 5, 6, 7, 8, 9, 10], "habitat": "brackish"},
    {"name": "Shrimp", "classIndex": 31, "scientificName": "Penaeus monodon", "genus": "Penaeus", "family": "Penaeidae", "englishName": "Shrimp", "localName": "Hipon / Sugpo",
     "weightRange": [0.01, 0.15], "pricePerKg": [300, 600], "peakMonths": [10, 11, 12, 1, 2, 3, 4], "habitat": "marine"},
    {"name": "Silver Barb", "classIndex": 32, "scientificName": "Barbonymus gonionotus", "genus": "Barbonymus", "family": "Cyprinidae", "englishName": "Silver Barb", "localName": "Silver Barb",
     "weightRange": [0.1, 1.0], "pricePerKg": [80, 140], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Silver Carp", "classIndex": 33, "scientificName": "Hypophthalmichthys molitrix", "genus": "Hypophthalmichthys", "family": "Cyprinidae", "englishName": "Silver Carp", "localName": "Silver Carp",
     "weightRange": [1.0, 15.0], "pricePerKg": [70, 130], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Silver Perch", "classIndex": 34, "scientificName": "Leiopotherapon plumbeus", "genus": "Leiopotherapon", "family": "Terapontidae", "englishName": "Silver Perch", "localName": "Ayungin",
     "weightRange": [0.02, 0.15], "pricePerKg": [250, 500], "peakMonths": [1, 2, 3, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Snakehead", "classIndex": 35, "scientificName": "Channa striata", "genus": "Channa", "family": "Channidae", "englishName": "Snakehead", "localName": "Dalag",
     "weightRange": [0.3, 3.0], "pricePerKg": [180, 320], "peakMonths": [6, 7, 8, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Striped Red Mullet", "classIndex": 36, "scientificName": "Mullus surmuletus", "genus": "Mullus", "family": "Mullidae", "englishName": "Striped Red Mullet", "localName": "Striped Red Mullet",
     "weightRange": [0.05, 0.4], "pricePerKg": [200, 380], "peakMonths": [4, 5, 6, 7, 8, 9], "habitat": "marine"},
    {"name": "Tenpounder", "classIndex": 37, "scientificName": "Elops machnata", "genus": "Elops", "family": "Elopidae", "englishName": "Tenpounder", "localName": "Bidbid",
     "weightRange": [0.3, 3.0], "pricePerKg": [100, 180], "peakMonths": [3, 4, 5, 6, 7, 8, 9], "habitat": "marine"},
    {"name": "Tilapia", "classIndex": 38, "scientificName": "Oreochromis niloticus", "genus": "Oreochromis", "family": "Cichlidae", "englishName": "Tilapia", "localName": "Tilapia",
     "weightRange": [0.2, 1.5], "pricePerKg": [100, 180], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Trout", "classIndex": 39, "scientificName": "Oncorhynchus mykiss", "genus": "Oncorhynchus", "family": "Salmonidae", "englishName": "Trout", "localName": "Trout",
     "weightRange": [0.3, 5.0], "pricePerKg": [350, 600], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "freshwater"},
    {"name": "Tuna", "classIndex": 40, "scientificName": "Thunnus albacares", "genus": "Thunnus", "family": "Scombridae", "englishName": "Yellowfin Tuna", "localName": "Barilis / Tambakol",
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
