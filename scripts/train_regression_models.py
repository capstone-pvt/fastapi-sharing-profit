"""Train scikit-learn regression models for weight estimation and price prediction.

Expected input (created by exporter.py):
    <export-root>/
        weight_data.csv – columns: image,species,classIndex,weightKg,
                          pricePerKg,lengthCm,widthCm,scaleReferenceCm,
                          bboxX,bboxY,bboxWidth,bboxHeight
        price_data.csv  – columns: image,species,classIndex,weightKg,pricePerKg

Output:
    models/weight/weight_model.joblib
    models/price/price_model.joblib

Weight model features (matching inference.py):
    [species_index, bbox_width, bbox_height, scale_reference_cm, length_cm, width_cm]

Price model features (matching inference.py):
    [species_index, weight_kg]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import cross_val_score


def _safe_float(val: str, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if np.isfinite(v) else default
    except (ValueError, TypeError):
        return default


def train_weight_model(export_root: Path, output_path: Path) -> None:
    csv_path = export_root / "weight_data.csv"
    if not csv_path.exists():
        print("weight_data.csv not found – skipping weight model training.")
        return

    X_rows: list[list[float]] = []
    y_rows: list[float] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            weight = _safe_float(row.get("weightKg", ""))
            if weight <= 0:
                continue
            features = [
                _safe_float(row.get("classIndex", "")),
                _safe_float(row.get("bboxWidth", "")),
                _safe_float(row.get("bboxHeight", "")),
                _safe_float(row.get("scaleReferenceCm", "")),
                _safe_float(row.get("lengthCm", "")),
                _safe_float(row.get("widthCm", "")),
            ]
            X_rows.append(features)
            y_rows.append(weight)

    if len(X_rows) < 2:
        print(f"Not enough weight samples ({len(X_rows)}) – need at least 2. Skipping.")
        return

    X = np.array(X_rows, dtype=float)
    y = np.array(y_rows, dtype=float)

    model = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )

    # Cross-validation score if enough samples
    if len(X) >= 5:
        cv_folds = min(5, len(X))
        scores = cross_val_score(model, X, y, cv=cv_folds, scoring="r2")
        print(f"Weight model CV R²: {scores.mean():.4f} (+/- {scores.std():.4f})")

    model.fit(X, y)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    print(f"Weight model saved to {output_path} ({len(X)} samples)")


def train_price_model(export_root: Path, output_path: Path) -> None:
    csv_path = export_root / "price_data.csv"
    if not csv_path.exists():
        print("price_data.csv not found – skipping price model training.")
        return

    X_rows: list[list[float]] = []
    y_rows: list[float] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            price = _safe_float(row.get("pricePerKg", ""))
            weight = _safe_float(row.get("weightKg", ""))
            if price <= 0 or weight <= 0:
                continue
            features = [
                _safe_float(row.get("classIndex", "")),
                weight,
            ]
            X_rows.append(features)
            y_rows.append(price)

    if len(X_rows) < 2:
        print(f"Not enough price samples ({len(X_rows)}) – need at least 2. Skipping.")
        return

    X = np.array(X_rows, dtype=float)
    y = np.array(y_rows, dtype=float)

    model = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )

    if len(X) >= 5:
        cv_folds = min(5, len(X))
        scores = cross_val_score(model, X, y, cv=cv_folds, scoring="r2")
        print(f"Price model CV R²: {scores.mean():.4f} (+/- {scores.std():.4f})")

    model.fit(X, y)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    print(f"Price model saved to {output_path} ({len(X)} samples)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train weight and price regression models from exported CSV data."
    )
    parser.add_argument(
        "--export-root",
        required=True,
        help="Path to the exported fish-training directory.",
    )
    parser.add_argument(
        "--weight-output",
        default="models/weight/weight_model.joblib",
        help="Output path for weight model (default: models/weight/weight_model.joblib).",
    )
    parser.add_argument(
        "--price-output",
        default="models/price/price_model.joblib",
        help="Output path for price model (default: models/price/price_model.joblib).",
    )
    args = parser.parse_args()

    export_root = Path(args.export_root)
    if not export_root.exists():
        raise SystemExit(f"Export root not found: {export_root}")

    train_weight_model(export_root, Path(args.weight_output))
    train_price_model(export_root, Path(args.price_output))


if __name__ == "__main__":
    main()
