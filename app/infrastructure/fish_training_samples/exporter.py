from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


def export_dataset(
    *,
    samples: list[dict[str, Any]],
    species_records: list[dict[str, Any]],
    include_images: bool,
) -> dict[str, Any]:
    timestamp = int(datetime.utcnow().timestamp() * 1000)
    export_root = Path("exports") / "fish-training" / str(timestamp)
    images_dir = export_root / "images"
    labels_dir = export_root / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    class_index_by_name = {
        record.get("name"): record.get("classIndex")
        for record in species_records
    }

    if not class_index_by_name:
        unique_species = sorted({s.get("species") for s in samples if s.get("species")})
        class_index_by_name = {name: idx for idx, name in enumerate(unique_species)}

    weight_rows = [
        "image,species,classIndex,weightKg,pricePerKg,lengthCm,widthCm,scaleReferenceCm,bboxX,bboxY,bboxWidth,bboxHeight"
    ]
    price_rows = ["image,species,classIndex,weightKg,pricePerKg"]
    images_count = 0
    labels_count = 0
    price_samples = 0

    for sample in samples:
        image_path = Path(sample.get("imagePath", ""))
        if not image_path.exists():
            continue
        ext = image_path.suffix or ".jpg"
        image_file = f"{sample['_id']}{ext}"
        dest_image = images_dir / image_file

        if include_images:
            dest_image.write_bytes(image_path.read_bytes())
            images_count += 1

        class_index = class_index_by_name.get(sample.get("species"), -1)
        bbox = sample.get("bbox") or {}
        bbox_x = bbox_y = bbox_w = bbox_h = ""
        if bbox and class_index >= 0:
            with Image.open(image_path) as img:
                width, height = img.size
            if width and height:
                try:
                    if all(
                        bbox.get(key) is not None
                        for key in ("x", "y", "width", "height")
                    ):
                        x_center = (bbox["x"] + bbox["width"] / 2) / width
                        y_center = (bbox["y"] + bbox["height"] / 2) / height
                        width_norm = bbox["width"] / width
                        height_norm = bbox["height"] / height
                        label_line = (
                            f"{class_index} {x_center:.6f} {y_center:.6f} "
                            f"{width_norm:.6f} {height_norm:.6f}"
                        )
                        (labels_dir / f"{sample['_id']}.txt").write_text(
                            label_line + "\n"
                        )
                        labels_count += 1
                        bbox_x = str(bbox["x"])
                        bbox_y = str(bbox["y"])
                        bbox_w = str(bbox["width"])
                        bbox_h = str(bbox["height"])
                except Exception:
                    pass

        weight_rows.append(
            ",".join(
                [
                    image_file,
                    str(sample.get("species") or ""),
                    str(class_index),
                    str(sample.get("weightKg") or ""),
                    str(sample.get("pricePerKg") or ""),
                    str(sample.get("lengthCm") or ""),
                    str(sample.get("widthCm") or ""),
                    str(sample.get("scaleReferenceCm") or ""),
                    bbox_x,
                    bbox_y,
                    bbox_w,
                    bbox_h,
                ]
            )
        )
        if sample.get("pricePerKg") is not None:
            price_rows.append(
                ",".join(
                    [
                        image_file,
                        str(sample.get("species") or ""),
                        str(class_index),
                        str(sample.get("weightKg") or ""),
                        str(sample.get("pricePerKg") or ""),
                    ]
                )
            )
            price_samples += 1

    (export_root / "weight_data.csv").write_text("\n".join(weight_rows) + "\n")
    (export_root / "price_data.csv").write_text("\n".join(price_rows) + "\n")
    classes = [
        name for name, _ in sorted(class_index_by_name.items(), key=lambda x: x[1])
    ]
    (export_root / "classes.txt").write_text("\n".join(classes) + "\n")
    (export_root / "manifest.json").write_text(
        json.dumps(
            {
                "createdAt": datetime.utcnow().isoformat(),
                "samples": len(samples),
                "images": images_count,
                "labels": labels_count,
                "priceSamples": price_samples,
                "classes": classes,
                "exportRoot": str(export_root),
            },
            indent=2,
        )
    )

    return {
        "exportRoot": str(export_root),
        "samples": len(samples),
        "images": images_count,
        "labels": labels_count,
        "priceSamples": price_samples,
        "classes": classes,
    }
