"""Train fish classifier to a target accuracy (default: 90%).

This script:
  1. Downloads Kaggle datasets (if not already present)
  2. Builds classification dataset (train/val split)
  3. Trains a YOLO classifier with optimized augmentation settings
  4. Evaluates on validation set
  5. If accuracy < target, retrains with larger model / more epochs
  6. Repeats until target is met or max retries exhausted

Usage:
    # Full pipeline (download + train + evaluate):
    PYTHONPATH=. python scripts/train_to_target_accuracy.py

    # Use existing dataset:
    PYTHONPATH=. python scripts/train_to_target_accuracy.py --export-root exports/kaggle/merged

    # Custom target accuracy:
    PYTHONPATH=. python scripts/train_to_target_accuracy.py --target-accuracy 0.95

    # Skip download (use cached data):
    PYTHONPATH=. python scripts/train_to_target_accuracy.py --skip-download
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


# Training configurations to try in order (escalating model size + epochs)
TRAINING_STAGES = [
    {
        "name": "Stage 1: Small model, moderate epochs",
        "model": "yolov8s-cls.pt",
        "epochs": 30,
        "imgsz": 224,
        "batch": 32,
    },
    {
        "name": "Stage 2: Medium model, more epochs",
        "model": "yolov8m-cls.pt",
        "epochs": 50,
        "imgsz": 224,
        "batch": 16,
    },
    {
        "name": "Stage 3: Medium model, high resolution",
        "model": "yolov8m-cls.pt",
        "epochs": 80,
        "imgsz": 320,
        "batch": 16,
    },
    {
        "name": "Stage 4: Large model, maximum effort",
        "model": "yolov8l-cls.pt",
        "epochs": 100,
        "imgsz": 320,
        "batch": 8,
    },
]


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n> {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def _latest_weight_file(base_dir: Path) -> Path | None:
    candidates = list(base_dir.glob("**/weights/best.pt"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _evaluate(
    model_path: str,
    val_dir: str,
    use_tta: bool = True,
) -> float:
    """Run evaluation and return top-1 accuracy."""
    cmd = [
        "python", "scripts/evaluate_models.py",
        "--classifier-model", model_path,
        "--val-dir", val_dir,
        "--output-json", "eval_results.json",
    ]
    if not use_tta:
        cmd.append("--no-tta")

    result = _run(cmd, check=False)
    if result.returncode != 0:
        print("Warning: Evaluation script failed")
        return 0.0

    import json
    try:
        data = json.loads(Path("eval_results.json").read_text(encoding="utf-8"))
        return data.get("top1_accuracy", 0.0)
    except Exception:
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train fish classifier to target accuracy."
    )
    parser.add_argument(
        "--export-root",
        help="Use existing export directory (skip download).",
    )
    parser.add_argument(
        "--target-accuracy",
        type=float,
        default=0.90,
        help="Target top-1 accuracy (default: 0.90 = 90%%).",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download step (use cached data).",
    )
    parser.add_argument(
        "--max-per-class",
        type=int,
        default=300,
        help="Max images per class from Kaggle (default: 300).",
    )
    parser.add_argument(
        "--dataset-presets",
        nargs="+",
        default=["large-scale", "ph-fish"],
        help="Kaggle dataset presets to download (default: large-scale ph-fish).",
    )
    parser.add_argument(
        "--start-stage",
        type=int,
        default=1,
        choices=[1, 2, 3, 4],
        help="Start from training stage N (default: 1).",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up datasets and runs after training.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    models_dir = project_root / "app" / "models"
    classifier_output = models_dir / "classifier" / "best.pt"

    print(f"{'='*60}")
    print(f"  Fish Classifier Training Pipeline")
    print(f"  Target accuracy: {args.target_accuracy:.0%}")
    print(f"{'='*60}")

    # Step 1: Get training data
    export_root: Path
    if args.export_root:
        export_root = Path(args.export_root)
        if not export_root.exists():
            raise SystemExit(f"Export root not found: {export_root}")
        print(f"\nUsing existing export: {export_root}")
    else:
        print(f"\nStep 1: Downloading datasets...")
        preset_args = []
        for p in args.dataset_presets:
            preset_args.extend(["--presets", p]) if not preset_args else preset_args.append(p)

        download_cmd = [
            "python", "scripts/download_kaggle_dataset.py",
            "--presets", *args.dataset_presets,
            "--max-per-class", str(args.max_per_class),
        ]
        if args.skip_download:
            download_cmd.append("--skip-download")

        result = _run(download_cmd, check=False)
        if result.returncode != 0:
            raise SystemExit("Failed to download datasets. Check Kaggle credentials.")

        export_root = Path("exports/kaggle/merged")
        if not export_root.exists():
            raise SystemExit(f"Export root not created: {export_root}")

    # Step 2: Build classification dataset
    print(f"\nStep 2: Building classification dataset...")
    dataset_dir = Path("datasets/fish_species")
    _run([
        "python", "scripts/build_classification_dataset.py",
        "--export-root", str(export_root),
        "--output", str(dataset_dir),
        "--val-ratio", "0.2",
    ])

    val_dir = dataset_dir / "val"
    if not val_dir.exists():
        raise SystemExit(f"Validation directory not created: {val_dir}")

    # Step 3: Train with escalating configurations until target met
    stages = TRAINING_STAGES[args.start_stage - 1:]
    best_accuracy = 0.0
    best_model_path = str(classifier_output)

    for i, stage in enumerate(stages, start=args.start_stage):
        print(f"\n{'='*60}")
        print(f"  {stage['name']}")
        print(f"  Model: {stage['model']}, Epochs: {stage['epochs']}, ImgSz: {stage['imgsz']}")
        print(f"{'='*60}")

        train_cmd = [
            "yolo", "classify", "train",
            f"data={dataset_dir}",
            f"model={stage['model']}",
            f"epochs={stage['epochs']}",
            f"imgsz={stage['imgsz']}",
            f"batch={stage['batch']}",
            "patience=15",
            # Data augmentation
            "augment=True",
            "hsv_h=0.015",
            "hsv_s=0.7",
            "hsv_v=0.4",
            "degrees=15",
            "translate=0.1",
            "scale=0.5",
            "shear=5.0",
            "fliplr=0.5",
            "flipud=0.0",
            "mosaic=0.5",
            "mixup=0.15",
            "erasing=0.1",
            # Optimization
            "optimizer=AdamW",
            "lr0=0.001",
            "lrf=0.01",
            "warmup_epochs=3",
            "cos_lr=True",
            "label_smoothing=0.1",
        ]

        result = _run(train_cmd, check=False)
        if result.returncode != 0:
            print(f"Warning: Training failed at {stage['name']}")
            continue

        # Find best weights
        trained_weights = _latest_weight_file(project_root / "runs" / "classify")
        if not trained_weights:
            print("Warning: No trained weights found")
            continue

        # Copy to model directory
        classifier_output.parent.mkdir(parents=True, exist_ok=True)
        classifier_output.write_bytes(trained_weights.read_bytes())
        print(f"Model saved to: {classifier_output}")

        # Evaluate
        print(f"\nEvaluating {stage['name']}...")
        accuracy = _evaluate(str(classifier_output), str(val_dir), use_tta=True)
        print(f"\n  Top-1 Accuracy: {accuracy:.1%}")

        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_model_path = str(classifier_output)

        if accuracy >= args.target_accuracy:
            print(f"\n  TARGET MET: {accuracy:.1%} >= {args.target_accuracy:.0%}")
            break
        else:
            print(f"\n  Below target ({accuracy:.1%} < {args.target_accuracy:.0%}), trying next stage...")

    # Final report
    print(f"\n{'='*60}")
    print(f"  TRAINING COMPLETE")
    print(f"{'='*60}")
    print(f"  Best accuracy: {best_accuracy:.1%}")
    print(f"  Target:        {args.target_accuracy:.0%}")
    print(f"  Model:         {best_model_path}")

    if best_accuracy >= args.target_accuracy:
        print(f"\n  RESULT: PASSED ({best_accuracy:.1%} >= {args.target_accuracy:.0%})")
    else:
        print(f"\n  RESULT: BELOW TARGET ({best_accuracy:.1%} < {args.target_accuracy:.0%})")
        print(f"  Suggestions:")
        print(f"    - Add more training images per species")
        print(f"    - Download additional datasets: --dataset-presets large-scale ph-fish nature-conservancy")
        print(f"    - Increase --max-per-class (current: {args.max_per_class})")
        print(f"    - Run again with --start-stage 4 for maximum model size")

    # Cleanup
    if args.cleanup:
        for d in [
            project_root / "datasets",
            project_root / "runs",
            project_root / "exports",
        ]:
            if d.exists():
                shutil.rmtree(d)
                print(f"Cleaned up: {d}")
        eval_json = Path("eval_results.json")
        if eval_json.exists():
            eval_json.unlink()

    if best_accuracy < args.target_accuracy:
        sys.exit(1)


if __name__ == "__main__":
    main()
