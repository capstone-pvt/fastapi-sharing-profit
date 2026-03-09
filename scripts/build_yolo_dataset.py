"""Build a YOLO detection dataset from an exported fish-training directory.

Expected input layout (created by exporter.py):
    <export-root>/
        images/      – raw images named <sampleId>.<ext>
        labels/      – YOLO-format .txt files (classIdx cx cy w h)
        classes.txt  – one class name per line

Output:
    fish_dataset.yaml        – YOLO data config pointing to split dirs
    datasets/fish_detect/
        images/
            train/
            val/
        labels/
            train/
            val/
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build YOLO detection dataset from exported samples."
    )
    parser.add_argument(
        "--export-root",
        required=True,
        help="Path to the exported fish-training directory.",
    )
    parser.add_argument(
        "--output",
        default="datasets/fish_detect",
        help="Output dataset directory (default: datasets/fish_detect).",
    )
    parser.add_argument(
        "--yaml-out",
        default="fish_dataset.yaml",
        help="Path for the YOLO data YAML file (default: fish_dataset.yaml).",
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
    labels_dir = export_root / "labels"
    output_dir = Path(args.output)

    if not images_dir.exists():
        raise SystemExit(f"Images directory not found: {images_dir}")
    if not labels_dir.exists():
        raise SystemExit(f"Labels directory not found: {labels_dir}")

    # Read class names
    classes_file = export_root / "classes.txt"
    if classes_file.exists():
        class_names = [
            line.strip() for line in classes_file.read_text().splitlines() if line.strip()
        ]
    else:
        raise SystemExit("classes.txt not found – cannot build detection dataset.")

    # Collect paired image + label files
    label_stems = {lf.stem for lf in labels_dir.glob("*.txt") if lf.stat().st_size > 0}
    pairs: list[tuple[Path, Path]] = []
    for img_file in sorted(images_dir.iterdir()):
        if img_file.stem in label_stems:
            label_file = labels_dir / f"{img_file.stem}.txt"
            pairs.append((img_file, label_file))

    if not pairs:
        raise SystemExit("No image-label pairs found.")

    # Shuffle and split
    random.seed(args.seed)
    random.shuffle(pairs)
    split_idx = max(1, int(len(pairs) * (1 - args.val_ratio)))
    train_pairs = pairs[:split_idx]
    val_pairs = pairs[split_idx:] if len(pairs) > 1 else []

    # Create output structure
    if output_dir.exists():
        shutil.rmtree(output_dir)

    for split_name, split_pairs in [("train", train_pairs), ("val", val_pairs)]:
        img_out = output_dir / "images" / split_name
        lbl_out = output_dir / "labels" / split_name
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)
        for img_file, lbl_file in split_pairs:
            shutil.copy2(img_file, img_out / img_file.name)
            shutil.copy2(lbl_file, lbl_out / lbl_file.name)

    # Write YOLO data YAML
    data_yaml = {
        "path": str(output_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "nc": len(class_names),
        "names": class_names,
    }
    yaml_path = Path(args.yaml_out)
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data_yaml, f, default_flow_style=False, sort_keys=False)

    print(f"Detection dataset built at: {output_dir}")
    print(f"  Classes: {len(class_names)} ({', '.join(class_names)})")
    print(f"  Train:   {len(train_pairs)} image-label pairs")
    print(f"  Val:     {len(val_pairs)} image-label pairs")
    print(f"  YAML:    {yaml_path}")


if __name__ == "__main__":
    main()
