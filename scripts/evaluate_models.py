"""Evaluate fish classification and detection model accuracy.

Usage:
    # Evaluate classifier on a validation dataset:
    PYTHONPATH=. python scripts/evaluate_models.py --val-dir datasets/fish_species/val

    # Evaluate classifier on an export root (auto-splits data):
    PYTHONPATH=. python scripts/evaluate_models.py --export-root exports/kaggle/merged

    # Evaluate with custom model path:
    PYTHONPATH=. python scripts/evaluate_models.py --val-dir datasets/fish_species/val --classifier-model app/models/classifier/best.pt

    # Evaluate and require minimum accuracy (exit code 1 if below):
    PYTHONPATH=. python scripts/evaluate_models.py --val-dir datasets/fish_species/val --min-accuracy 0.90

Output:
    Per-class accuracy, confusion matrix, top-1 and top-5 accuracy,
    and a summary report.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".jfif"}


def _discover_val_images(val_dir: Path) -> dict[str, list[Path]]:
    """Discover validation images organized as val/<ClassName>/image.jpg."""
    class_images: dict[str, list[Path]] = {}
    if not val_dir.exists():
        return class_images
    for class_dir in sorted(val_dir.iterdir()):
        if not class_dir.is_dir():
            continue
        images = [
            f for f in class_dir.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        ]
        if images:
            class_images[class_dir.name] = images
    return class_images


def _build_val_from_export(export_root: Path, val_ratio: float = 0.2) -> Path:
    """Build a temporary validation set from an export directory."""
    import csv

    images_dir = export_root / "images"
    weight_csv = export_root / "weight_data.csv"

    if not images_dir.exists() or not weight_csv.exists():
        raise SystemExit(f"Export root must contain images/ and weight_data.csv: {export_root}")

    # Parse species mapping
    image_to_species: dict[str, str] = {}
    with open(weight_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            img = row.get("image", "").strip()
            species = row.get("species", "").strip()
            if img and species:
                image_to_species[img] = species

    # Group by species
    species_images: dict[str, list[Path]] = defaultdict(list)
    for img_name, species in image_to_species.items():
        img_path = images_dir / img_name
        if img_path.exists():
            species_images[species].append(img_path)

    # Create temp val directory with val_ratio split
    tmp_val = Path("_eval_tmp_val")
    if tmp_val.exists():
        shutil.rmtree(tmp_val)

    random.seed(42)
    total_val = 0
    for species, images in species_images.items():
        random.shuffle(images)
        val_count = max(1, int(len(images) * val_ratio))
        val_images = images[:val_count]

        species_dir = tmp_val / species
        species_dir.mkdir(parents=True, exist_ok=True)
        for img in val_images:
            shutil.copy2(img, species_dir / img.name)
            total_val += 1

    print(f"Built temp validation set: {total_val} images across {len(species_images)} species")
    return tmp_val


def evaluate_classifier(
    model_path: str,
    val_dir: Path,
    use_tta: bool = True,
    max_per_class: int = 0,
) -> dict:
    """Evaluate classifier accuracy on a validation directory.

    Returns a dict with top1_accuracy, top5_accuracy, per_class results,
    and confusion data.
    """
    from PIL import Image, ImageOps, ImageEnhance
    from ultralytics import YOLO
    import numpy as np

    model = YOLO(model_path)
    model_names = model.names  # {idx: name}
    class_images = _discover_val_images(val_dir)

    if not class_images:
        print(f"ERROR: No validation images found in {val_dir}")
        return {"top1_accuracy": 0.0, "top5_accuracy": 0.0}

    print(f"\nEvaluating classifier: {model_path}")
    print(f"Validation dir: {val_dir}")
    print(f"Model classes: {len(model_names)}")
    print(f"Val classes: {len(class_images)} ({sum(len(v) for v in class_images.values())} images)")
    if use_tta:
        print("TTA: enabled (original + horizontal flip)")
    print()

    # Results tracking
    total = 0
    top1_correct = 0
    top5_correct = 0
    per_class: dict[str, dict] = {}
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for true_class, images in sorted(class_images.items()):
        if max_per_class > 0:
            images = images[:max_per_class]

        class_total = 0
        class_top1 = 0
        class_top5 = 0

        for img_path in images:
            try:
                pil_img = Image.open(img_path).convert("RGB")
                # Apply same preprocessing as inference pipeline
                pil_img = ImageOps.exif_transpose(pil_img) or pil_img
                pil_img = ImageEnhance.Sharpness(pil_img).enhance(1.3)
                pil_img = ImageEnhance.Contrast(pil_img).enhance(1.1)

                # Get predictions
                results = model.predict(pil_img, verbose=False)
                if not results or not hasattr(results[0], "probs"):
                    continue

                probs = results[0].probs.data.cpu().numpy()
                names = results[0].names

                if use_tta:
                    # Horizontal flip TTA
                    flipped = ImageOps.mirror(pil_img)
                    results_flip = model.predict(flipped, verbose=False)
                    if results_flip and hasattr(results_flip[0], "probs"):
                        probs_flip = results_flip[0].probs.data.cpu().numpy()
                        probs = (probs + probs_flip) / 2.0

                # Top-1 and Top-5
                top_indices = np.argsort(probs)[::-1]
                predicted_class = names.get(top_indices[0], "Unknown")
                top5_classes = [names.get(i, "Unknown") for i in top_indices[:5]]

                class_total += 1
                total += 1

                # Case-insensitive matching
                true_lower = true_class.lower()
                pred_lower = predicted_class.lower()

                if true_lower == pred_lower:
                    top1_correct += 1
                    class_top1 += 1

                if any(true_lower == c.lower() for c in top5_classes):
                    top5_correct += 1
                    class_top5 += 1

                confusion[true_class][predicted_class] += 1

            except Exception as e:
                print(f"  Warning: Failed to process {img_path.name}: {e}")
                continue

        if class_total > 0:
            acc = class_top1 / class_total
            top5_acc = class_top5 / class_total
            per_class[true_class] = {
                "total": class_total,
                "top1_correct": class_top1,
                "top1_accuracy": round(acc, 4),
                "top5_correct": class_top5,
                "top5_accuracy": round(top5_acc, 4),
            }
            status = "PASS" if acc >= 0.9 else "FAIL" if acc < 0.7 else "WARN"
            print(f"  [{status}] {true_class:30s}  top1={acc:6.1%}  top5={top5_acc:6.1%}  ({class_top1}/{class_total})")

    # Summary
    top1_accuracy = top1_correct / total if total > 0 else 0.0
    top5_accuracy = top5_correct / total if total > 0 else 0.0

    print(f"\n{'='*60}")
    print(f"  OVERALL RESULTS")
    print(f"{'='*60}")
    print(f"  Total images evaluated: {total}")
    print(f"  Top-1 Accuracy: {top1_accuracy:.1%} ({top1_correct}/{total})")
    print(f"  Top-5 Accuracy: {top5_accuracy:.1%} ({top5_correct}/{total})")
    print(f"  Classes evaluated: {len(per_class)}")

    # Show worst performing classes
    if per_class:
        worst = sorted(per_class.items(), key=lambda x: x[1]["top1_accuracy"])[:5]
        if worst and worst[0][1]["top1_accuracy"] < 1.0:
            print(f"\n  Worst performing classes:")
            for cls_name, stats in worst:
                print(f"    {cls_name}: {stats['top1_accuracy']:.1%}")

    # Show most common misclassifications
    print(f"\n  Top misclassifications:")
    misclass: list[tuple[str, str, int]] = []
    for true_cls, preds in confusion.items():
        for pred_cls, count in preds.items():
            if true_cls.lower() != pred_cls.lower():
                misclass.append((true_cls, pred_cls, count))
    misclass.sort(key=lambda x: x[2], reverse=True)
    for true_cls, pred_cls, count in misclass[:10]:
        print(f"    {true_cls} -> {pred_cls}: {count} times")

    return {
        "model_path": model_path,
        "val_dir": str(val_dir),
        "total_images": total,
        "top1_accuracy": round(top1_accuracy, 4),
        "top5_accuracy": round(top5_accuracy, 4),
        "top1_correct": top1_correct,
        "top5_correct": top5_correct,
        "classes_evaluated": len(per_class),
        "use_tta": use_tta,
        "per_class": per_class,
        "evaluated_at": datetime.utcnow().isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate fish classification model accuracy."
    )
    parser.add_argument(
        "--val-dir",
        help="Validation directory (val/<ClassName>/images).",
    )
    parser.add_argument(
        "--export-root",
        help="Export root to auto-split into val set.",
    )
    parser.add_argument(
        "--classifier-model",
        default="app/models/classifier/best.pt",
        help="Path to classifier model (default: app/models/classifier/best.pt).",
    )
    parser.add_argument(
        "--no-tta",
        action="store_true",
        help="Disable Test-Time Augmentation.",
    )
    parser.add_argument(
        "--max-per-class",
        type=int,
        default=0,
        help="Max images to evaluate per class (0 = all).",
    )
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=0.0,
        help="Minimum required top-1 accuracy (0.0-1.0). Exit code 1 if below.",
    )
    parser.add_argument(
        "--output-json",
        help="Save detailed results to JSON file.",
    )
    args = parser.parse_args()

    if not args.val_dir and not args.export_root:
        parser.error("Either --val-dir or --export-root is required.")

    tmp_val = None
    if args.val_dir:
        val_dir = Path(args.val_dir)
    else:
        val_dir = _build_val_from_export(Path(args.export_root))
        tmp_val = val_dir

    if not val_dir.exists():
        raise SystemExit(f"Validation directory not found: {val_dir}")

    try:
        results = evaluate_classifier(
            model_path=args.classifier_model,
            val_dir=val_dir,
            use_tta=not args.no_tta,
            max_per_class=args.max_per_class,
        )
    finally:
        # Clean up temp val dir
        if tmp_val and tmp_val.exists():
            shutil.rmtree(tmp_val)

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nResults saved to: {output_path}")

    # Check minimum accuracy threshold
    if args.min_accuracy > 0:
        if results["top1_accuracy"] >= args.min_accuracy:
            print(f"\n  PASSED: {results['top1_accuracy']:.1%} >= {args.min_accuracy:.1%} minimum")
        else:
            print(f"\n  FAILED: {results['top1_accuracy']:.1%} < {args.min_accuracy:.1%} minimum")
            sys.exit(1)


if __name__ == "__main__":
    main()
