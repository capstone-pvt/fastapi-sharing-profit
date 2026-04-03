from __future__ import annotations

import argparse
import asyncio
import csv
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from app.db import connect_db, disconnect_db
from app.infrastructure.fish_models.repository import create_model as repo_create_model
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


def _parse_yolo_results(train_dir: Path) -> dict:
    """Parse YOLO training results from results.csv."""
    results_csv = train_dir / "results.csv"
    if not results_csv.exists():
        return {}
    rows = []
    with open(results_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    if not rows:
        return {}
    last = rows[-1]
    # Classification results have top1_acc and top5_acc columns
    top1 = last.get("metrics/accuracy_top1", last.get("top1_acc", ""))
    top5 = last.get("metrics/accuracy_top5", last.get("top5_acc", ""))
    loss = last.get("train/loss", last.get("loss", ""))
    return {
        "top1Accuracy": float(top1) if top1 else None,
        "top5Accuracy": float(top5) if top5 else None,
        "finalLoss": float(loss) if loss else None,
        "totalEpochs": len(rows),
    }


def _count_species(export_root: Path) -> tuple[int, list[str]]:
    """Read classes.txt to get species count and names."""
    classes_file = export_root / "classes.txt"
    if not classes_file.exists():
        return 0, []
    names = [l.strip() for l in classes_file.read_text().splitlines() if l.strip()]
    return len(names), names


def _count_images(export_root: Path) -> int:
    """Count images in the export directory."""
    images_dir = export_root / "images"
    if not images_dir.exists():
        return 0
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".jfif"}
    return sum(1 for f in images_dir.iterdir() if f.suffix.lower() in exts)


async def _save_training_record(
    model_type: str,
    model_path: str,
    export_root: Path,
    train_dir: Path | None,
    epochs: int,
) -> None:
    """Save training metadata to fish_models collection in MongoDB."""
    results = _parse_yolo_results(train_dir) if train_dir else {}
    species_count, species_names = _count_species(export_root)
    image_count = _count_images(export_root)
    now = datetime.utcnow()

    record = {
        "modelType": model_type,
        "version": now.strftime("%Y%m%d_%H%M%S"),
        "modelPath": model_path,
        "description": f"Trained on {image_count} images, {species_count} species, {epochs} epochs",
        "isActive": True,
        "status": "completed",
        "trainingMetrics": {
            "top1Accuracy": results.get("top1Accuracy"),
            "top5Accuracy": results.get("top5Accuracy"),
            "finalLoss": results.get("finalLoss"),
            "epochs": results.get("totalEpochs", epochs),
        },
        "datasetInfo": {
            "totalImages": image_count,
            "speciesCount": species_count,
            "speciesNames": species_names,
        },
        "trainedAt": now,
        "createdAt": now,
        "updatedAt": now,
    }

    doc = await repo_create_model(record)
    print(f"Training record saved to database (id: {doc.get('id', doc.get('_id'))})")
    if results.get("top1Accuracy") is not None:
        print(f"  Top-1 Accuracy: {results['top1Accuracy']:.1%}")
        print(f"  Top-5 Accuracy: {results['top5Accuracy']:.1%}")
    print(f"  Species: {species_count}, Images: {image_count}, Epochs: {epochs}")


def _select_model_size(num_images: int, model_type: str, requested: str | None) -> str:
    """Auto-select YOLO model size based on dataset size and type.

    Larger datasets can support larger models without overfitting.
    - < 100 images: nano (yolov8n) - prevents overfitting on tiny datasets
    - 100-500 images: small (yolov8s) - good balance
    - 500-2000 images: medium (yolov8m) - better accuracy
    - > 2000 images: large (yolov8l) - best accuracy for large datasets
    """
    if requested:
        return requested

    suffix = "-cls.pt" if model_type == "classify" else ".pt"

    if num_images < 100:
        return f"yolov8n{suffix}"
    elif num_images < 500:
        return f"yolov8s{suffix}"
    elif num_images < 2000:
        return f"yolov8m{suffix}"
    else:
        return f"yolov8l{suffix}"


def _select_epochs(num_images: int, requested: int | None) -> int:
    """Auto-adjust epochs based on dataset size when not explicitly set.

    Small datasets need more epochs; large datasets converge faster.
    Pass --epochs-classify / --epochs-detect to override.
    """
    if requested is not None:
        return requested

    if num_images < 50:
        return 50
    elif num_images < 200:
        return 40
    elif num_images < 500:
        return 30
    elif num_images < 2000:
        return 25
    else:
        return 20


def main() -> None:
    parser = argparse.ArgumentParser(description="Automate dataset + model training.")
    parser.add_argument(
        "--export-root",
        help="Use existing export (exports/fish-training/<timestamp>).",
    )
    parser.add_argument("--epochs-classify", type=int, default=None,
                        help="Training epochs for classifier. Auto-selected by dataset size if omitted.")
    parser.add_argument("--epochs-detect", type=int, default=None,
                        help="Training epochs for detector. Auto-selected by dataset size if omitted.")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument(
        "--model-classify",
        default=None,
        help="YOLO classification model (e.g. yolov8s-cls.pt). Auto-selected if omitted.",
    )
    parser.add_argument(
        "--model-detect",
        default=None,
        help="YOLO detection model (e.g. yolov8s.pt). Auto-selected if omitted.",
    )
    parser.add_argument("--skip-detect", action="store_true")
    parser.add_argument("--skip-classify", action="store_true")
    parser.add_argument("--skip-regression", action="store_true")
    parser.add_argument(
        "--patience",
        type=int,
        default=10,
        help="Early stopping patience: stop if no improvement for N epochs (default: 10).",
    )
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=0.0,
        help="Minimum classifier accuracy (0.0-1.0). Prints warning if below (default: 0 = no check).",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete datasets, exports, downloads, and training runs after training to save disk space.",
    )
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

    # Count dataset size for auto-tuning
    num_images = _count_images(export_root)
    print(f"Dataset size: {num_images} images")

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

    # Auto-select model sizes
    classify_model = _select_model_size(num_images, "classify", args.model_classify)
    detect_model = _select_model_size(num_images, "detect", args.model_detect)
    classify_epochs = _select_epochs(num_images, args.epochs_classify)
    detect_epochs = _select_epochs(num_images, args.epochs_detect)

    print(f"Training config:")
    print(f"  Classifier: model={classify_model}, epochs={classify_epochs}, imgsz={args.imgsz}")
    print(f"  Detector:   model={detect_model}, epochs={detect_epochs}, imgsz={args.imgsz}")
    print(f"  Patience:   {args.patience}")

    # Train classification model with enhanced settings
    if not args.skip_classify:
        _run(
            [
                "yolo",
                "classify",
                "train",
                "data=datasets/fish_species",
                f"model={classify_model}",
                f"epochs={classify_epochs}",
                f"imgsz={args.imgsz}",
                f"patience={args.patience}",
                # Data augmentation for better generalization
                "augment=True",
                "hsv_h=0.015",      # Hue variation (lighting changes)
                "hsv_s=0.7",        # Saturation variation (water color)
                "hsv_v=0.4",        # Value/brightness variation
                "degrees=10",       # Slight rotation
                "translate=0.1",    # Slight translation
                "scale=0.5",        # Scale variation
                "fliplr=0.5",       # Horizontal flip (fish face both ways)
                "flipud=0.0",       # No vertical flip (fish don't swim upside down)
                "mosaic=0.5",       # Mosaic augmentation (mix multiple images)
                "mixup=0.1",        # MixUp augmentation
                "erasing=0.1",      # Random erasing (occlusion robustness)
                # Optimization
                "optimizer=AdamW",   # Better convergence than SGD for small datasets
                "lr0=0.001",         # Initial learning rate
                "lrf=0.01",          # Final learning rate factor
                "warmup_epochs=3",   # Warmup for stable training
                "cos_lr=True",       # Cosine learning rate schedule
                "label_smoothing=0.1",  # Prevents overconfident predictions
            ]
        )

    # Train detection model with enhanced settings
    if can_detect:
        _run(
            [
                "yolo",
                "detect",
                "train",
                "data=fish_dataset.yaml",
                f"model={detect_model}",
                f"epochs={detect_epochs}",
                f"imgsz={args.imgsz}",
                f"patience={args.patience}",
                # Data augmentation
                "augment=True",
                "hsv_h=0.015",
                "hsv_s=0.7",
                "hsv_v=0.4",
                "degrees=10",
                "translate=0.1",
                "scale=0.5",
                "fliplr=0.5",
                "flipud=0.0",
                "mosaic=1.0",        # Full mosaic for detection
                "mixup=0.1",
                "copy_paste=0.1",    # Copy-paste augmentation for detection
                # Optimization
                "optimizer=AdamW",
                "lr0=0.001",
                "lrf=0.01",
                "warmup_epochs=3",
                "cos_lr=True",
                "label_smoothing=0.05",
                # Detection-specific
                "nms=True",
            ]
        )

    # Train regression models
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
    models_dir = project_root / "app" / "models"
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

    # Post-training accuracy validation
    classifier_path = models_dir / "classifier" / "best.pt"
    val_dir = Path("datasets/fish_species/val")
    if classify_best and not args.skip_classify and val_dir.exists():
        print(f"\n{'='*60}")
        print("  POST-TRAINING ACCURACY EVALUATION")
        print(f"{'='*60}")
        eval_result = subprocess.run(
            [
                "python", "scripts/evaluate_models.py",
                "--classifier-model", str(classifier_path),
                "--val-dir", str(val_dir),
                "--output-json", "eval_results.json",
            ],
            check=False,
        )
        if eval_result.returncode == 0:
            import json
            try:
                eval_data = json.loads(Path("eval_results.json").read_text(encoding="utf-8"))
                accuracy = eval_data.get("top1_accuracy", 0.0)
                print(f"\n  Classifier Top-1 Accuracy: {accuracy:.1%}")
                if args.min_accuracy > 0:
                    if accuracy >= args.min_accuracy:
                        print(f"  PASSED: {accuracy:.1%} >= {args.min_accuracy:.0%}")
                    else:
                        print(f"  WARNING: {accuracy:.1%} < {args.min_accuracy:.0%} target")
                        print(f"  Consider: more data, larger model, or more epochs")
            except Exception:
                pass
            finally:
                Path("eval_results.json").unlink(missing_ok=True)

    # Save training records to database
    asyncio.run(connect_db())
    try:
        if classify_best and not args.skip_classify:
            classify_train_dir = classify_best.parents[1]
            asyncio.run(
                _save_training_record(
                    model_type="classifier",
                    model_path=str(models_dir / "classifier" / "best.pt"),
                    export_root=export_root,
                    train_dir=classify_train_dir,
                    epochs=classify_epochs,
                )
            )

        if detect_best and can_detect:
            detect_train_dir = detect_best.parents[1]
            asyncio.run(
                _save_training_record(
                    model_type="detector",
                    model_path=str(models_dir / "detector" / "best.pt"),
                    export_root=export_root,
                    train_dir=detect_train_dir,
                    epochs=detect_epochs,
                )
            )
    finally:
        asyncio.run(disconnect_db())

    # Cleanup large files to save disk space
    if args.cleanup:
        cleanup_dirs = [
            project_root / "datasets",
            project_root / "downloads",
            project_root / "exports",
            project_root / "runs",
        ]
        freed = 0
        for d in cleanup_dirs:
            if d.exists():
                size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                shutil.rmtree(d)
                freed += size
                print(f"Cleaned up: {d}")
        print(f"Freed {freed / (1024 * 1024):.1f} MB of disk space.")
        print("Model weights are preserved in models/")


if __name__ == "__main__":
    main()
