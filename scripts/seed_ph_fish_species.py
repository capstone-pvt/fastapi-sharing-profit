"""Seed Philippine fish species into the database.

Usage:
    cd profit_sharing_api_fastapi
    PYTHONPATH=. python scripts/seed_ph_fish_species.py

This script:
  1. Inserts Philippine fish species with scientific names, English names,
     local names, genus, and family into the fish_species collection.
  2. Skips species that already exist (matched by scientificName).
  3. Assigns classIndex values continuing from the highest existing index.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env BEFORE importing app modules (get_settings uses @lru_cache)
_project_root = Path(__file__).resolve().parents[1]
load_dotenv(_project_root / ".env")

from app.db import connect_db, disconnect_db, get_db  # noqa: E402

PH_FISH_SPECIES = [
    {
        "name": "Bullet Tuna",
        "scientificName": "Auxis rochei",
        "genus": "Auxis",
        "family": "Scombridae",
        "englishName": "Bullet Tuna",
        "localName": "Tambakol/Tulingan/Tangi/Bangkulis/Panit/Bantalaan/Bantaea-an/Bariles/Pakan/Pirit/Karaw/Barilis/Carao",
    },
    {
        "name": "Frigate Tuna",
        "scientificName": "Auxis thazard",
        "genus": "Auxis",
        "family": "Scombridae",
        "englishName": "Frigate Tuna",
        "localName": "Tulingan/Tangi/Bonito/Tulingan Lapad/Turingan/Aloy Mangko/Pirit/Bolis/Lapad/Pidlayan/Mangku",
    },
    {
        "name": "Yellowfin Tuna",
        "scientificName": "Thunnus albacares",
        "genus": "Thunnus",
        "family": "Scombridae",
        "englishName": "Yellowfin Tuna",
        "localName": "Tambakol/Tulingan/Tangi/Bangkulis/Panit/Bantalaan/Bantaea-an/Bariles/Pakan/Pirit/Karaw/Barilis/Carao",
    },
    {
        "name": "Bigeye Tuna",
        "scientificName": "Thunnus obesus",
        "genus": "Thunnus",
        "family": "Scombridae",
        "englishName": "Bigeye Tuna",
        "localName": "Barilis",
    },
    {
        "name": "Skipjack Tuna",
        "scientificName": "Katsuwonus pelamis",
        "genus": "Katsuwonus",
        "family": "Scombridae",
        "englishName": "Skipjack Tuna",
        "localName": "Tulingan/Tangi/Bonito/Tulingan Lapad/Turingan/Aloy Mangko/Pirit/Bolis/Lapad/Pidlayan/Mangku",
    },
    {
        "name": "Common Dolphin Fish",
        "scientificName": "Coryphaena hippurus",
        "genus": "Coryphaena",
        "family": "Coryphaenidae",
        "englishName": "Common Dolphin Fish",
        "localName": "Dorado/Duradu/Lamadang/Pandawan",
    },
    {
        "name": "Mackerel Scad",
        "scientificName": "Decapterus macarellus",
        "genus": "Decapterus",
        "family": "Carangidae",
        "englishName": "Mackerel Scad",
        "localName": "Balsa/Budloy",
    },
    {
        "name": "Rainbow Runner",
        "scientificName": "Elagatis bipinnulata",
        "genus": "Elagatis",
        "family": "Carangidae",
        "englishName": "Rainbow Runner",
        "localName": "Salmon/Malasalmon/Salindato/Malasolid/Man",
    },
    {
        "name": "Indo-Pacific Sailfish",
        "scientificName": "Istiophorus platypterus",
        "genus": "Istiophorus",
        "family": "Istiophoridae",
        "englishName": "Indo-Pacific Sailfish",
        "localName": "Malasugi/Marang/Solisogi/Liplipan",
    },
    {
        "name": "Black Marlin",
        "scientificName": "Istiompax indica",
        "genus": "Makaira",
        "family": "Istiophoridae",
        "englishName": "Black Marlin",
        "localName": "Malasugi",
    },
]


async def seed_species() -> None:
    db = get_db()
    collection = db["fish_species"]

    # Find the highest existing classIndex
    highest = await collection.find_one(sort=[("classIndex", -1)])
    next_index = (highest.get("classIndex", -1) + 1) if highest else 0

    now = datetime.utcnow()
    added = 0
    skipped = 0

    for species in PH_FISH_SPECIES:
        # Check if species already exists by scientificName
        existing = await collection.find_one(
            {"scientificName": species["scientificName"]}
        )
        if existing:
            print(f"  Skipped (exists): {species['name']} ({species['scientificName']})")
            skipped += 1
            continue

        doc = {
            **species,
            "classIndex": next_index,
            "isActive": True,
            "createdAt": now,
            "updatedAt": now,
        }
        await collection.insert_one(doc)
        print(f"  Added [{next_index}]: {species['name']} ({species['scientificName']}) - {species['localName']}")
        next_index += 1
        added += 1

    print(f"\nDone: {added} species added, {skipped} skipped (already existed).")


async def main() -> None:
    await connect_db()
    try:
        print("Seeding Philippine fish species...\n")
        await seed_species()
    finally:
        await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
