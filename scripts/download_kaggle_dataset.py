"""Download fish datasets from Kaggle and prepare them for the training pipeline.

Supported datasets:
  1. crowww/a-large-scale-fish-dataset  (default)
     - 9 species, ~1000 images each with GT segmentation masks
  2. the-nature-conservancy-fisheries-monitoring  (competition)
     - YFT (Yellowfin Tuna), BET (Bigeye Tuna), DOL (Dolphinfish/Mahi-Mahi),
       ALB (Albacore Tuna), and more
  3. markdaniellampa/fish-dataset
     - 31 Philippine freshwater/brackish species from Cabuyao City

Usage:
    # Download all supported datasets and merge into one:
    python scripts/download_kaggle_dataset.py --all

    # Download a single dataset:
    python scripts/download_kaggle_dataset.py --dataset crowww/a-large-scale-fish-dataset

    # Limit images per class:
    python scripts/download_kaggle_dataset.py --all --max-per-class 200

Output:
    exports/kaggle/merged/
        images/          - fish images from all datasets
        classes.txt      - one class name per line
        weight_data.csv  - species mapping for classification pipeline
        price_data.csv   - placeholder price data for regression pipeline
"""

from __future__ import annotations

import argparse
import csv
import random
import shutil
import zipfile
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".jfif"}

# --- Species name mapping ---
# Nature Conservancy competition folder abbreviations → species names
_NC_SPECIES_MAP: dict[str, str] = {
    "ALB": "Albacore Tuna",
    "BET": "Bigeye Tuna",
    "DOL": "Common Dolphin Fish",
    "LAG": "Opah",
    "SHARK": "Shark",
    "YFT": "Yellowfin Tuna",
    "OTHER": "",  # skip
    "NoF": "",    # skip (no fish)
}

# Large Scale Fish Dataset normalization
_LARGE_SCALE_NORMALIZE: dict[str, str] = {
    "Gilt Head Bream": "Gilt-Head Bream",
    "Horse Mackerel": "Hourse Mackerel",
}

# All known dataset slugs
DATASET_PRESETS: dict[str, dict] = {
    "large-scale": {
        "slug": "crowww/a-large-scale-fish-dataset",
        "type": "dataset",
        "description": "A Large Scale Fish Dataset (9 species)",
    },
    "nature-conservancy": {
        "slug": "the-nature-conservancy-fisheries-monitoring",
        "type": "competition",
        "description": "Nature Conservancy Fisheries Monitoring (YFT, BET, DOL, ALB)",
    },
    "ph-fish": {
        "slug": "markdaniellampa/fish-dataset",
        "type": "dataset",
        "description": "Philippine Fish Dataset (31 species from Cabuyao City)",
    },
}


def _ensure_kaggle() -> None:
    """Verify kaggle package is installed and credentials exist."""
    try:
        import kaggle  # noqa: F401
    except ImportError:
        raise SystemExit("kaggle package not installed. Run: pip install kaggle")
    except OSError as e:
        if "Could not find kaggle.json" in str(e):
            raise SystemExit(
                "Kaggle credentials not found.\n"
                "1. Go to https://www.kaggle.com/settings → Create New Token\n"
                "2. Save kaggle.json to ~/.kaggle/kaggle.json (or %USERPROFILE%\\.kaggle\\)\n"
                "3. Run this script again."
            )
        raise


def _download_dataset(slug: str, download_dir: Path, is_competition: bool = False) -> Path:
    """Download and extract a Kaggle dataset or competition."""
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()

    download_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {slug} ...")

    if is_competition:
        api.competition_download_files(slug, path=str(download_dir))
    else:
        api.dataset_download_files(slug, path=str(download_dir), unzip=True)

    # Extract any remaining zip files
    for zf in sorted(download_dir.glob("*.zip")):
        print(f"Extracting {zf.name} ...")
        with zipfile.ZipFile(zf, "r") as z:
            z.extractall(download_dir)
        zf.unlink()

    print(f"Downloaded to {download_dir}")
    return download_dir


def _find_class_folders(root: Path, species_map: dict[str, str] | None = None) -> dict[str, list[Path]]:
    """Find image class folders (species folders containing images)."""
    class_images: dict[str, list[Path]] = {}

    for folder in sorted(root.rglob("*")):
        if not folder.is_dir():
            continue

        images = [
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        ]
        if not images:
            continue

        # Skip ground-truth / mask folders
        name_upper = folder.name.upper().replace(" ", "").replace("_", "")
        if name_upper in ("GT", "MASKS", "ANNOTATIONS"):
            continue
        if folder.name.upper().rstrip().endswith(" GT") or folder.name.upper().endswith("_GT"):
            continue
        if any(p.upper() in ("GT", "MASKS", "ANNOTATIONS") for p in folder.parts):
            continue

        raw_name = folder.name.strip()

        # Apply species map if provided (e.g. Nature Conservancy abbreviations)
        if species_map is not None:
            class_name = species_map.get(raw_name, raw_name)
        else:
            class_name = raw_name.replace("_", " ").strip()
            class_name = _LARGE_SCALE_NORMALIZE.get(class_name, class_name)

        # Skip empty-mapped classes (e.g. "OTHER", "NoF")
        if not class_name:
            continue

        class_images.setdefault(class_name, []).extend(images)

    return class_images


def _collect_images_from_dir(
    raw_dir: Path,
    species_map: dict[str, str] | None = None,
) -> dict[str, list[Path]]:
    """Collect class→images mapping, filtering out GT/mask folders."""
    class_images = _find_class_folders(raw_dir, species_map)

    # Extra filter: remove images from GT subdirectories
    filtered: dict[str, list[Path]] = {}
    for class_name, images in class_images.items():
        non_gt = [
            img for img in images
            if not any(p.upper() in ("GT", "MASKS") for p in img.parts)
        ]
        if non_gt:
            filtered[class_name] = non_gt

    return filtered


def _write_export(
    class_images: dict[str, list[Path]],
    output_dir: Path,
    max_per_class: int,
) -> None:
    """Write the unified export (images/, classes.txt, CSVs)."""
    class_names = sorted(class_images.keys())

    images_out = output_dir / "images"
    images_out.mkdir(parents=True, exist_ok=True)

    classes_file = output_dir / "classes.txt"
    classes_file.write_text("\n".join(class_names) + "\n", encoding="utf-8")

    weight_rows: list[dict[str, str]] = []
    price_rows: list[dict[str, str]] = []
    image_count = 0

    random.seed(42)

    for class_idx, class_name in enumerate(class_names):
        images = list(class_images[class_name])
        random.shuffle(images)

        if max_per_class > 0:
            images = images[:max_per_class]

        for img_path in images:
            safe_name = class_name.replace(" ", "_").replace("-", "_")
            suffix = img_path.suffix.lower()
            if suffix == ".jfif":
                suffix = ".jpg"
            dest_name = f"{safe_name}_{image_count:05d}{suffix}"
            dest_path = images_out / dest_name
            shutil.copy2(img_path, dest_path)

            weight_rows.append({
                "image": dest_name,
                "species": class_name,
                "classIndex": str(class_idx),
                "weightKg": "",
                "pricePerKg": "",
                "lengthCm": "",
                "widthCm": "",
                "scaleReferenceCm": "",
                "bboxX": "0",
                "bboxY": "0",
                "bboxWidth": "0",
                "bboxHeight": "0",
            })

            price_rows.append({
                "image": dest_name,
                "species": class_name,
                "classIndex": str(class_idx),
                "weightKg": "",
                "pricePerKg": "",
            })

            image_count += 1

    # Write CSVs
    weight_csv = output_dir / "weight_data.csv"
    with open(weight_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "image", "species", "classIndex", "weightKg", "pricePerKg",
            "lengthCm", "widthCm", "scaleReferenceCm",
            "bboxX", "bboxY", "bboxWidth", "bboxHeight",
        ])
        writer.writeheader()
        writer.writerows(weight_rows)

    price_csv = output_dir / "price_data.csv"
    with open(price_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "image", "species", "classIndex", "weightKg", "pricePerKg",
        ])
        writer.writeheader()
        writer.writerows(price_rows)

    print(f"\nDataset prepared at: {output_dir}")
    print(f"  Species:  {len(class_names)}")
    for cn in class_names:
        count = min(len(class_images[cn]), max_per_class) if max_per_class > 0 else len(class_images[cn])
        print(f"    - {cn}: {count} images")
    print(f"  Total:    {image_count} images")
    print(f"  Files:    classes.txt, weight_data.csv, price_data.csv")


def _download_and_collect(
    preset_key: str,
    download_base: Path,
    skip_download: bool,
) -> dict[str, list[Path]]:
    """Download a preset dataset and return class→images mapping."""
    preset = DATASET_PRESETS[preset_key]
    slug = preset["slug"]
    is_competition = preset["type"] == "competition"
    slug_dir = slug.replace("/", "_")
    download_dir = download_base / slug_dir

    print(f"\n{'='*60}")
    print(f"  {preset['description']}")
    print(f"{'='*60}")

    if skip_download and download_dir.exists():
        print(f"Using existing download at {download_dir}")
    else:
        _download_dataset(slug, download_dir, is_competition)

    species_map = _NC_SPECIES_MAP if preset_key == "nature-conservancy" else None
    return _collect_images_from_dir(download_dir, species_map)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download fish datasets from Kaggle for training."
    )
    parser.add_argument(
        "--dataset",
        help="Kaggle dataset slug (e.g. crowww/a-large-scale-fish-dataset).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all supported datasets and merge them.",
    )
    parser.add_argument(
        "--presets",
        nargs="+",
        choices=list(DATASET_PRESETS.keys()),
        help="Download specific preset datasets (e.g. --presets large-scale nature-conservancy ph-fish).",
    )
    parser.add_argument(
        "--download-dir",
        default="downloads/kaggle",
        help="Directory for raw downloads (default: downloads/kaggle).",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory (default: exports/kaggle/merged or exports/kaggle/<slug>).",
    )
    parser.add_argument(
        "--max-per-class",
        type=int,
        default=0,
        help="Max images per species (0 = all, default: 0).",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download if data already exists.",
    )
    args = parser.parse_args()

    _ensure_kaggle()

    download_base = Path(args.download_dir)
    merged_images: dict[str, list[Path]] = {}

    if args.all:
        # Download all presets
        preset_keys = list(DATASET_PRESETS.keys())
        output_dir = Path(args.output_dir) if args.output_dir else Path("exports/kaggle/merged")

        for key in preset_keys:
            try:
                class_images = _download_and_collect(key, download_base, args.skip_download)
                for species, imgs in class_images.items():
                    merged_images.setdefault(species, []).extend(imgs)
            except Exception as e:
                print(f"\nWarning: Failed to process {key}: {e}")
                print("Continuing with other datasets...")

    elif args.presets:
        # Download specific presets
        output_dir = Path(args.output_dir) if args.output_dir else Path("exports/kaggle/merged")

        for key in args.presets:
            try:
                class_images = _download_and_collect(key, download_base, args.skip_download)
                for species, imgs in class_images.items():
                    merged_images.setdefault(species, []).extend(imgs)
            except Exception as e:
                print(f"\nWarning: Failed to process {key}: {e}")
                print("Continuing with other datasets...")

    elif args.dataset:
        # Single dataset (custom slug)
        slug_dir = args.dataset.replace("/", "_")
        output_dir = Path(args.output_dir) if args.output_dir else Path("exports/kaggle") / slug_dir
        download_dir = download_base / slug_dir

        if args.skip_download and download_dir.exists():
            print(f"Using existing download at {download_dir}")
        else:
            _download_dataset(args.dataset, download_dir)

        merged_images = _collect_images_from_dir(download_dir)

    else:
        # Default: download large-scale + nature-conservancy
        output_dir = Path(args.output_dir) if args.output_dir else Path("exports/kaggle/merged")

        for key in ["large-scale", "nature-conservancy"]:
            try:
                class_images = _download_and_collect(key, download_base, args.skip_download)
                for species, imgs in class_images.items():
                    merged_images.setdefault(species, []).extend(imgs)
            except Exception as e:
                print(f"\nWarning: Failed to process {key}: {e}")

    if not merged_images:
        raise SystemExit("No images found in any dataset.")

    # Prepare output
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_export(merged_images, output_dir, args.max_per_class)

    print(f"\n{'='*60}")
    print("Next steps:")
    print(f"{'='*60}")
    print(f"\n  # Train with auto_train (classification only):")
    print(f"  PYTHONPATH=. python scripts/auto_train.py --export-root {output_dir} --skip-detect --skip-regression --cleanup")
    print(f"\n  # Or build classification dataset manually:")
    print(f"  python scripts/build_classification_dataset.py --export-root {output_dir}")
    print(f"  yolo classify train data=datasets/fish_species model=yolov8n-cls.pt epochs=10")


if __name__ == "__main__":
    main()
