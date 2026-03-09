"""Build a YOLO classification dataset from an exported fish-training directory.

Expected input layout (created by exporter.py):
    <export-root>/
        images/         – raw images named <sampleId>.<ext>
        classes.txt     – one class name per line
        weight_data.csv – header: image,species,classIndex,...

Output layout (for `yolo classify train data=datasets/fish_species`):
    datasets/fish_species/
        train/
            <ClassName>/   – 80 % of images
        val/
            <ClassName>/   – 20 % of images
"""

from __future__ import annotations

import argparse
import csv
import random
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build YOLO classification dataset from exported samples."
    )
    parser.add_argument(
        "--export-root",
        required=True,
        help="Path to the exported fish-training directory.",
    )
    parser.add_argument(
        "--output",
        default="datasets/fish_species",
        help="Output dataset directory (default: datasets/fish_species).",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.2,
        help="Fraction of images used for validation (default: 0.2).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    export_root = Path(args.export_root)
    images_dir = export_root / "images"
    weight_csv = export_root / "weight_data.csv"
    output_dir = Path(args.output)

    if not images_dir.exists():
        raise SystemExit(f"Images directory not found: {images_dir}")
    if not weight_csv.exists():
        raise SystemExit(f"weight_data.csv not found: {weight_csv}")

    # Read class names
    classes_file = export_root / "classes.txt"
    if classes_file.exists():
        class_names = [
            line.strip() for line in classes_file.read_text().splitlines() if line.strip()
        ]
    else:
        class_names = []

    # Parse weight_data.csv to map image filename -> species
    image_to_species: dict[str, str] = {}
    with open(weight_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            img = row.get("image", "").strip()
            species = row.get("species", "").strip()
            if img and species:
                image_to_species[img] = species

    if not image_to_species:
        raise SystemExit("No valid image-species mappings found in weight_data.csv.")

    # Discover species if classes.txt was missing
    if not class_names:
        class_names = sorted(set(image_to_species.values()))

    # Group images by species
    species_images: dict[str, list[Path]] = {name: [] for name in class_names}
    for img_name, species in image_to_species.items():
        img_path = images_dir / img_name
        if img_path.exists() and species in species_images:
            species_images[species].append(img_path)

    total = sum(len(v) for v in species_images.values())
    if total == 0:
        raise SystemExit("No images found for any species.")

    # Create output dirs
    if output_dir.exists():
        shutil.rmtree(output_dir)
    train_dir = output_dir / "train"
    val_dir = output_dir / "val"

    random.seed(args.seed)

    train_count = 0
    val_count = 0

    for species, images in species_images.items():
        if not images:
            continue

        (train_dir / species).mkdir(parents=True, exist_ok=True)
        (val_dir / species).mkdir(parents=True, exist_ok=True)

        random.shuffle(images)
        split_idx = max(1, int(len(images) * (1 - args.val_ratio)))
        train_imgs = images[:split_idx]
        val_imgs = images[split_idx:] if len(images) > 1 else []

        for img in train_imgs:
            shutil.copy2(img, train_dir / species / img.name)
            train_count += 1
        for img in val_imgs:
            shutil.copy2(img, val_dir / species / img.name)
            val_count += 1

    print(f"Classification dataset built at: {output_dir}")
    print(f"  Classes: {len(class_names)} ({', '.join(class_names)})")
    print(f"  Train:   {train_count} images")
    print(f"  Val:     {val_count} images")


if __name__ == "__main__":
    main()
