#!/usr/bin/env python
"""Interactive helper to record ground-truth pixels-per-cm for a QA image.

Usage:
    python scripts/measure_ground_truth.py <image_path> --reference-type coin_php_5 --cm 5.0

Shows the image in an OpenCV window. Click two points on a ruler that are
--cm centimeters apart. Press ENTER to confirm, R to reset, Q to quit.
On confirm:
    - Copies the image into tests/fixtures/reference_qa/images/ (unless already there).
    - Appends a row to tests/fixtures/reference_qa/ground_truth.csv.
"""
from __future__ import annotations

import argparse
import csv
import math
import shutil
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.fish.reference_types import ReferenceType  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "reference_qa"
IMAGES_DIR = FIXTURE_DIR / "images"
CSV_PATH = FIXTURE_DIR / "ground_truth.csv"

WINDOW = "Measure ruler (click 2 points, ENTER=save, R=reset, Q=quit)"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record ground-truth pixels-per-cm by clicking two ruler points.")
    p.add_argument("image", type=Path, help="Path to the QA image.")
    p.add_argument(
        "--reference-type",
        required=True,
        choices=[t.value for t in ReferenceType if t != ReferenceType.MANUAL],
        help="Which reference object is in the image.",
    )
    p.add_argument(
        "--cm",
        type=float,
        required=True,
        help="Known distance in centimeters between the two points you will click on the ruler.",
    )
    return p.parse_args()


def _fit_to_screen(img, max_side: int = 1200):
    h, w = img.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale >= 1.0:
        return img, 1.0
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA), scale


def main() -> int:
    args = _parse_args()
    if not args.image.exists():
        print(f"ERROR: image not found: {args.image}")
        return 1
    if args.cm <= 0:
        print("ERROR: --cm must be positive")
        return 1

    img_full = cv2.imread(str(args.image))
    if img_full is None:
        print(f"ERROR: OpenCV could not read {args.image}")
        return 1

    display, scale = _fit_to_screen(img_full)
    points: list[tuple[int, int]] = []

    def _on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 2:
            points.append((x, y))

    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW, _on_mouse)

    while True:
        canvas = display.copy()
        for i, (x, y) in enumerate(points):
            cv2.circle(canvas, (x, y), 6, (0, 255, 0), -1)
            cv2.putText(canvas, str(i + 1), (x + 8, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        if len(points) == 2:
            cv2.line(canvas, points[0], points[1], (0, 255, 255), 2)
            dx = points[1][0] - points[0][0]
            dy = points[1][1] - points[0][1]
            dist_display = math.hypot(dx, dy)
            dist_full = dist_display / scale
            ppc = dist_full / args.cm
            msg = f"{dist_full:.1f}px over {args.cm}cm -> {ppc:.2f} px/cm"
            cv2.putText(canvas, msg, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imshow(WINDOW, canvas)
        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):  # Q or ESC
            cv2.destroyAllWindows()
            print("Aborted.")
            return 1
        if key == ord("r"):
            points.clear()
        if key in (13, 10) and len(points) == 2:  # ENTER
            break

    cv2.destroyAllWindows()

    dx = points[1][0] - points[0][0]
    dy = points[1][1] - points[0][1]
    dist_full = math.hypot(dx, dy) / scale
    pixels_per_cm = dist_full / args.cm

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    dest = IMAGES_DIR / args.image.name
    if args.image.resolve() != dest.resolve():
        shutil.copy2(args.image, dest)

    rel_path = f"images/{dest.name}"
    new_row = {
        "filename": rel_path,
        "reference_type": args.reference_type,
        "ground_truth_pixels_per_cm": f"{pixels_per_cm:.4f}",
    }

    rows: list[dict[str, str]] = []
    if CSV_PATH.exists():
        with CSV_PATH.open(newline="") as f:
            rows = list(csv.DictReader(f))
    rows = [r for r in rows if r.get("filename") != rel_path]
    rows.append(new_row)

    with CSV_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "reference_type", "ground_truth_pixels_per_cm"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved: {rel_path}  type={args.reference_type}  px/cm={pixels_per_cm:.2f}")
    print(f"CSV rows now: {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
