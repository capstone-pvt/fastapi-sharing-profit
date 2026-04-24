"""Clear all training data so you can start fresh, one species at a time.

What it does:
  1. Drops `fish_species` collection in Mongo
  2. Drops `fish_training_samples` collection in Mongo
  3. Moves model artifacts (detector, classifier, weight, price) into
     `app/models/.backup_<timestamp>/` so they can be restored if needed

Usage:
    cd profit_sharing_api_fastapi
    PYTHONPATH=. python scripts/clear_training_data.py
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[1]
load_dotenv(_project_root / ".env")

from app.db import connect_db, disconnect_db, get_db  # noqa: E402


COLLECTIONS_TO_CLEAR = ["fish_species", "fish_training_samples"]

MODEL_FILES = [
    "classifier/best.pt",
    "classifier/best.pt.bak",
    "detector/best.pt",
    "weight/weight_model.joblib",
    "price/price_model.joblib",
]


async def clear_collections() -> None:
    await connect_db()
    db = get_db()
    existing = await db.list_collection_names()
    print("=" * 50)
    print("  DROPPING TRAINING COLLECTIONS")
    print("=" * 50)
    for name in COLLECTIONS_TO_CLEAR:
        if name in existing:
            await db[name].drop()
            print(f"  Dropped: {name}")
        else:
            print(f"  Skipped (not found): {name}")
    await disconnect_db()


def backup_model_files() -> None:
    models_root = _project_root / "app" / "models"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = models_root / f".backup_{stamp}"

    print()
    print("=" * 50)
    print("  BACKING UP MODEL ARTIFACTS")
    print("=" * 50)

    moved_any = False
    for rel in MODEL_FILES:
        src = models_root / rel
        if not src.exists():
            print(f"  Skipped (not found): {rel}")
            continue
        dest = backup_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        print(f"  Moved: {rel} -> {dest.relative_to(models_root)}")
        moved_any = True

    if moved_any:
        print(f"\n  Backup folder: {backup_root}")
    else:
        print("\n  No model files needed to be moved.")


async def main() -> None:
    await clear_collections()
    backup_model_files()
    print()
    print("=" * 50)
    print("  DONE")
    print("=" * 50)
    print()
    print("Species catalog and training samples are empty.")
    print("Model artifacts have been moved aside (restore from .backup_<ts>/ if needed).")
    print("You can now add species one at a time via the admin UI or POST /fish/species.")


if __name__ == "__main__":
    asyncio.run(main())
