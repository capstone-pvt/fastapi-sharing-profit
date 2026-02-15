from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from app.db import connect_db, disconnect_db
from app.infrastructure.fish_training_samples import exporter as training_exporter
from app.infrastructure.fish_training_samples.repository import (
    list_active_species as repo_list_active_species,
    list_all_samples as repo_list_all_samples,
)


def _latest_weight_file(base_dir: Path) -> Path | None:
    candidates = list(base_dir.glob("**/weights/best.pt"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _has_labels(labels_dir: Path) -> bool:
    if not labels_dir.exists():
        return False
    for label_file in labels_dir.glob("*.txt"):
        try:
            if label_file.read_text().strip():
                return True
        except Exception:
            continue
    return False


async def _export_samples(include_images: bool) -> Path:
    samples = await repo_list_all_samples()
    if not samples:
        raise RuntimeError("No training samples found.")
    species_records = await repo_list_active_species()
    result = training_exporter.export_dataset(
        samples=samples,
        species_records=species_records,
        include_images=include_images,
    )
    return Path(result["exportRoot"])


def _run(cmd: list[str]) -> None:
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Automate dataset + model training.")
    parser.add_argument(
        "--export-root",
        help="Use existing export (exports/fish-training/<timestamp>).",
    )
    parser.add_argument("--epochs-classify", type=int, default=10)
    parser.add_argument("--epochs-detect", type=int, default=10)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--skip-detect", action="store_true")
    parser.add_argument("--skip-classify", action="store_true")
    parser.add_argument("--skip-regression", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")

    export_root: Path
    if args.export_root:
        export_root = Path(args.export_root)
        if not export_root.exists():
            raise SystemExit(f"Export root not found: {export_root}")
    else:
        asyncio.run(connect_db())
        try:
            export_root = asyncio.run(_export_samples(include_images=True))
        finally:
            asyncio.run(disconnect_db())

    print(f"Export root: {export_root}")

    # Build datasets
    _run(
        [
            "python",
            "scripts/build_classification_dataset.py",
            "--export-root",
            str(export_root),
        ]
    )

    labels_dir = export_root / "labels"
    can_detect = _has_labels(labels_dir) and not args.skip_detect
    if can_detect:
        _run(
            [
                "python",
                "scripts/build_yolo_dataset.py",
                "--export-root",
                str(export_root),
            ]
        )

    # Train models
    if not args.skip_classify:
        _run(
            [
                "yolo",
                "classify",
                "train",
                "data=datasets/fish_species",
                "model=yolov8n-cls.pt",
                f"epochs={args.epochs_classify}",
            ]
        )

    if can_detect:
        _run(
            [
                "yolo",
                "detect",
                "train",
                "data=fish_dataset.yaml",
                "model=yolov8n.pt",
                f"epochs={args.epochs_detect}",
                f"imgsz={args.imgsz}",
            ]
        )

    if not args.skip_regression:
        _run(
            [
                "python",
                "scripts/train_regression_models.py",
                "--export-root",
                str(export_root),
            ]
        )

    # Copy best weights into models/
    models_dir = project_root / "models"
    (models_dir / "classifier").mkdir(parents=True, exist_ok=True)
    (models_dir / "detector").mkdir(parents=True, exist_ok=True)
    (models_dir / "weight").mkdir(parents=True, exist_ok=True)
    (models_dir / "price").mkdir(parents=True, exist_ok=True)

    classify_best = _latest_weight_file(project_root / "runs" / "classify")
    if classify_best:
        (models_dir / "classifier" / "best.pt").write_bytes(
            classify_best.read_bytes()
        )
        print(f"Updated classifier: {models_dir / 'classifier' / 'best.pt'}")

    detect_best = _latest_weight_file(project_root / "runs" / "detect")
    if detect_best:
        (models_dir / "detector" / "best.pt").write_bytes(detect_best.read_bytes())
        print(f"Updated detector: {models_dir / 'detector' / 'best.pt'}")
    else:
        print("No detector weights found (skipped or no labels).")


if __name__ == "__main__":
    main()
