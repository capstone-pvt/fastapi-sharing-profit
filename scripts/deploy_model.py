"""Deploy a newly trained classifier model.

Copies the best.pt from the training run to the production model directory
and verifies the class list.

Usage:
    cd profit_sharing_api_fastapi
    PYTHONPATH=. python scripts/deploy_model.py [--run-dir runs/classify/fish_species_v2]
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Deploy trained classifier model")
    parser.add_argument(
        "--run-dir",
        default="runs/classify/fish_species_v2",
        help="Training run directory containing weights/best.pt",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    source = run_dir / "weights" / "best.pt"
    dest = Path("app/models/classifier/best.pt")

    if not source.exists():
        print(f"ERROR: {source} not found. Training may not have completed.")
        return

    # Backup old model
    if dest.exists():
        backup = dest.with_suffix(".pt.bak")
        shutil.copy2(dest, backup)
        print(f"Backed up old model to {backup}")

    # Copy new model
    shutil.copy2(source, dest)
    size_mb = dest.stat().st_size / 1024 / 1024
    print(f"Deployed {source} -> {dest} ({size_mb:.1f} MB)")

    # Verify classes
    try:
        from ultralytics import YOLO

        model = YOLO(str(dest))
        names = model.names
        print(f"\nModel has {len(names)} classes:")
        tuna_classes = [
            (idx, name) for idx, name in sorted(names.items()) if "tuna" in name.lower()
        ]
        if tuna_classes:
            print("  Tuna species:")
            for idx, name in tuna_classes:
                print(f"    [{idx:3d}] {name}")
        else:
            print("  WARNING: No tuna classes found!")

        # Check training results
        results_csv = run_dir / "results.csv"
        if results_csv.exists():
            lines = results_csv.read_text().strip().split("\n")
            last = lines[-1].split(",")
            epoch = last[0]
            top1 = float(last[3]) * 100
            top5 = float(last[4]) * 100
            print(f"\n  Training: {epoch} epochs")
            print(f"  Top-1 Accuracy: {top1:.1f}%")
            print(f"  Top-5 Accuracy: {top5:.1f}%")
    except Exception as e:
        print(f"  Could not verify: {e}")

    print("\nDone! Restart the API server to load the new model.")
    print("For production: push to git and Render will rebuild the Docker image.")


if __name__ == "__main__":
    main()
