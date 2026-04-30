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
    Base (6):       [species_index, bbox_width, bbox_height, scale_reference_cm, length_cm, width_cm]
    Engineered (3): [area (bbox_w*bbox_h), aspect_ratio (bbox_w/bbox_h), area_cm (length_cm*width_cm)]
    Total: 9 features — WEIGHT_MODEL_EXPECTED_FEATURES in inference.py must match this count.

Price model features (matching inference.py):
    [species_index, weight_kg]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


def _safe_float(val: str, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if np.isfinite(v) else default
    except (ValueError, TypeError):
        return default


def _add_engineered_features(X: np.ndarray) -> np.ndarray:
    """Add engineered features for better weight prediction.

    Input columns (7 base):
      [species_index, bbox_width, bbox_height, scale_ref,
       length_cm, width_cm, height_cm]
    Added columns (3 engineered): [bbox_area, bbox_aspect, volume_cm]

    Total: 10 features. Must match estimator.estimate_weight()
    AND model_loader.WEIGHT_MODEL_EXPECTED_FEATURES.

    height_cm is real-world container/fish height (cm). For Individual
    scans where height is unknown, pass 0 — volume_cm becomes 0, so the
    feature naturally degenerates without breaking the column count.
    """
    bbox_w = X[:, 1]
    bbox_h = X[:, 2]
    length_cm = X[:, 4]
    width_cm = X[:, 5]
    height_cm = X[:, 6]

    bbox_area = (bbox_w * bbox_h).reshape(-1, 1)
    bbox_aspect = np.where(
        bbox_h > 0, bbox_w / np.maximum(bbox_h, 1.0), 1.0
    ).reshape(-1, 1)
    volume_cm = (length_cm * width_cm * height_cm).reshape(-1, 1)

    return np.hstack([X, bbox_area, bbox_aspect, volume_cm])


def train_weight_model(export_root: Path, output_path: Path) -> None:
    csv_path = export_root / "weight_data.csv"
    if not csv_path.exists():
        print("weight_data.csv not found -- skipping weight model training.")
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
                _safe_float(row.get("heightCm", "")),
            ]
            X_rows.append(features)
            y_rows.append(weight)

    if len(X_rows) < 2:
        print(f"Not enough weight samples ({len(X_rows)}) -- need at least 2. Skipping.")
        return

    X = np.array(X_rows, dtype=float)
    y = np.array(y_rows, dtype=float)

    # Add engineered features
    X = _add_engineered_features(X)
    print(f"Weight model: {len(X)} samples, {X.shape[1]} features (7 base + 3 engineered)")

    # Select best model via cross-validation
    if len(X) >= 10:
        cv_folds = min(5, len(X))

        # Compare GradientBoosting with tuned hyperparameters
        param_grid = {
            "regressor__n_estimators": [100, 200, 300],
            "regressor__max_depth": [3, 4, 5, 6],
            "regressor__learning_rate": [0.05, 0.1, 0.15],
            "regressor__subsample": [0.8, 1.0],
        }
        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", GradientBoostingRegressor(random_state=42)),
        ])
        grid = GridSearchCV(
            pipeline,
            param_grid,
            cv=cv_folds,
            scoring="r2",
            n_jobs=-1,
            refit=True,
        )
        grid.fit(X, y)
        best_gbr = grid.best_estimator_
        best_gbr_score = grid.best_score_

        # Compare with RandomForest
        rf_pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", RandomForestRegressor(
                n_estimators=200, max_depth=6, random_state=42, n_jobs=-1
            )),
        ])
        rf_scores = cross_val_score(rf_pipeline, X, y, cv=cv_folds, scoring="r2")
        rf_score = rf_scores.mean()

        print(f"Weight model GBR CV R²: {best_gbr_score:.4f} (best params: {grid.best_params_})")
        print(f"Weight model RF  CV R²: {rf_score:.4f} (+/- {rf_scores.std():.4f})")

        if rf_score > best_gbr_score:
            print("  -> Using RandomForest (better R²)")
            rf_pipeline.fit(X, y)
            model = rf_pipeline
        else:
            print("  -> Using GradientBoosting (better R²)")
            model = best_gbr
    else:
        # Too few samples for grid search
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", GradientBoostingRegressor(
                n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42
            )),
        ])
        model.fit(X, y)

        if len(X) >= 5:
            cv_folds = min(5, len(X))
            scores = cross_val_score(model, X, y, cv=cv_folds, scoring="r2")
            print(f"Weight model CV R²: {scores.mean():.4f} (+/- {scores.std():.4f})")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    print(f"Weight model saved to {output_path} ({len(X)} samples)")


def train_price_model(export_root: Path, output_path: Path) -> None:
    csv_path = export_root / "price_data.csv"
    if not csv_path.exists():
        print("price_data.csv not found -- skipping price model training.")
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
        print(f"Not enough price samples ({len(X_rows)}) -- need at least 2. Skipping.")
        return

    X = np.array(X_rows, dtype=float)
    y = np.array(y_rows, dtype=float)

    # Select best model via cross-validation
    if len(X) >= 10:
        cv_folds = min(5, len(X))

        param_grid = {
            "regressor__n_estimators": [100, 200, 300],
            "regressor__max_depth": [3, 4, 5],
            "regressor__learning_rate": [0.05, 0.1, 0.15],
        }
        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", GradientBoostingRegressor(random_state=42)),
        ])
        grid = GridSearchCV(
            pipeline,
            param_grid,
            cv=cv_folds,
            scoring="r2",
            n_jobs=-1,
            refit=True,
        )
        grid.fit(X, y)
        model = grid.best_estimator_
        print(f"Price model CV R²: {grid.best_score_:.4f} (best params: {grid.best_params_})")
    else:
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", GradientBoostingRegressor(
                n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42
            )),
        ])
        model.fit(X, y)

        if len(X) >= 5:
            cv_folds = min(5, len(X))
            scores = cross_val_score(model, X, y, cv=cv_folds, scoring="r2")
            print(f"Price model CV R²: {scores.mean():.4f} (+/- {scores.std():.4f})")

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
        default="app/models/weight/weight_model.joblib",
        help="Output path for weight model (default: app/models/weight/weight_model.joblib).",
    )
    parser.add_argument(
        "--price-output",
        default="app/models/price/price_model.joblib",
        help="Output path for price model (default: app/models/price/price_model.joblib).",
    )
    args = parser.parse_args()

    export_root = Path(args.export_root)
    if not export_root.exists():
        raise SystemExit(f"Export root not found: {export_root}")

    train_weight_model(export_root, Path(args.weight_output))
    train_price_model(export_root, Path(args.price_output))


if __name__ == "__main__":
    main()
