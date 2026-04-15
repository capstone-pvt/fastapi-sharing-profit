#!/usr/bin/env python
"""Run the reference-QA image set and print a pass/fail table."""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.fish.reference_types import ReferenceType  # noqa: E402
from app.infrastructure.fish.reference_detector import (  # noqa: E402
    detect_reference_object,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "reference_qa"
TOLERANCE = 0.10


def main() -> int:
    csv_path = FIXTURE_DIR / "ground_truth.csv"
    if not csv_path.exists():
        print(f"No ground_truth.csv at {csv_path}")
        return 1

    per_type_totals: dict[str, list[bool]] = defaultdict(list)
    print(f"{'filename':<50} {'type':<14} {'truth':>8} {'pred':>8} {'err%':>7} status")
    print("-" * 100)

    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            path = FIXTURE_DIR / row["filename"]
            ref_type = ReferenceType(row["reference_type"])
            truth = float(row["ground_truth_pixels_per_cm"])
            if not path.exists():
                print(f"{row['filename']:<50} MISSING FILE")
                per_type_totals[ref_type.value].append(False)
                continue
            img = Image.open(path)
            result = detect_reference_object(img, ref_type)
            if result.status != "detected" or result.pixels_per_cm is None:
                print(f"{row['filename']:<50} {ref_type.value:<14} {truth:>8.2f} {'n/a':>8} {'—':>7} NOT_FOUND")
                per_type_totals[ref_type.value].append(False)
                continue
            pred = result.pixels_per_cm
            err = abs(pred - truth) / truth
            ok = err <= TOLERANCE
            per_type_totals[ref_type.value].append(ok)
            print(
                f"{row['filename']:<50} {ref_type.value:<14} {truth:>8.2f} "
                f"{pred:>8.2f} {err*100:>6.1f}% {'PASS' if ok else 'FAIL'}"
            )

    print()
    print("Per-type summary (target: >=80% pass):")
    all_good = True
    for ref_type, results in sorted(per_type_totals.items()):
        pass_rate = sum(results) / len(results) if results else 0.0
        status = "OK" if pass_rate >= 0.80 else "FAIL"
        print(f"  {ref_type:<14} {sum(results)}/{len(results)} pass ({pass_rate*100:.0f}%) - {status}")
        if pass_rate < 0.80:
            all_good = False
    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(main())
