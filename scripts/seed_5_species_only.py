"""Replace `fish_species` with the five species the trained classifier emits.

Use this against PROD (or any environment) after deploying the new classifier
in `app/models/classifier/best.pt`. The classifier outputs classIndex 0..4 —
this script makes the `fish_species` collection match.

Behavior:
  1. Drops every existing doc in `fish_species`.
  2. Inserts five canonical species with classIndex 0..4 in alphabetical
     order — same order the classifier was trained with.

Idempotent: re-running it produces the same five docs.

Usage:
    cd profit_sharing_api_fastapi
    # MAKE SURE MONGODB_URI in .env points at the target database first.
    PYTHONPATH=. python scripts/seed_5_species_only.py
    # or pass --dry-run to preview without writing.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[1]
load_dotenv(_project_root / ".env")

from app.db import connect_db, disconnect_db, get_db  # noqa: E402


SPECIES_FIVE: list[dict] = [
    {
        "name": "Auxis rochei",
        "classIndex": 0,
        "scientificName": "Auxis rochei",
        "genus": "Auxis",
        "family": "Scombridae",
        "englishName": "Bullet tuna",
        "localName": "Mangko/Pirit",
    },
    {
        "name": "Elagatis bipinnulata",
        "classIndex": 1,
        "scientificName": "Elagatis bipinnulata",
        "genus": "Elagatis",
        "family": "Carangidae",
        "englishName": "Rainbow runner",
        "localName": "Salindatu/Salmon",
    },
    {
        "name": "Euthynnus affinis",
        "classIndex": 2,
        "scientificName": "Euthynnus affinis",
        "genus": "Euthynnus",
        "family": "Scombridae",
        "englishName": "Eastern little tuna",
        "localName": "Patikan/Tulingan",
    },
    {
        "name": "Katsuwonus pelamis",
        "classIndex": 3,
        "scientificName": "Katsuwonus pelamis",
        "genus": "Katsuwonus",
        "family": "Scombridae",
        "englishName": "Skipjack tuna",
        "localName": "Sambagon/Tulingan/Bulis",
    },
    {
        "name": "Thunnus albacares",
        "classIndex": 4,
        "scientificName": "Thunnus albacares",
        "genus": "Thunnus",
        "family": "Scombridae",
        "englishName": "Yellowfin tuna",
        "localName": "Barilis/Bariles/Karaw",
    },
]


async def replace_species(*, dry_run: bool) -> None:
    db = get_db()
    coll = db["fish_species"]
    before = await coll.count_documents({})
    print(f"  fish_species before: {before} doc(s)")

    if dry_run:
        print("  --dry-run set: skipping delete + insert.")
        for sp in SPECIES_FIVE:
            print(f"    [{sp['classIndex']}] {sp['name']} ({sp['scientificName']})")
        return

    delete_result = await coll.delete_many({})
    print(f"  Deleted: {delete_result.deleted_count}")

    now = datetime.now(timezone.utc)
    docs = [
        {**sp, "isActive": True, "createdAt": now, "updatedAt": now}
        for sp in SPECIES_FIVE
    ]
    insert_result = await coll.insert_many(docs)
    print(f"  Inserted: {len(insert_result.inserted_ids)}")
    for sp in SPECIES_FIVE:
        print(f"    [{sp['classIndex']}] {sp['name']} ({sp['scientificName']})")

    after = await coll.count_documents({})
    print(f"  fish_species after:  {after} doc(s)")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset fish_species to the 5 trained-classifier classes."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without modifying the collection.",
    )
    args = parser.parse_args()

    print("=" * 56)
    print("  RE-SEED fish_species TO 5 TRAINED CLASSES")
    print("=" * 56)

    await connect_db()
    try:
        await replace_species(dry_run=args.dry_run)
    finally:
        await disconnect_db()

    print()
    print("Done. Verify in Mongo:")
    print("  db.fish_species.find({}, {name:1, classIndex:1}).sort({classIndex:1})")


if __name__ == "__main__":
    asyncio.run(main())
