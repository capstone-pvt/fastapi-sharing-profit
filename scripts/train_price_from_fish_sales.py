"""Train the price-per-kg regressor from real broker data in fish_sales.

The Excel ground-truth files have no pricePerKg column. The fish_sales
collection in prod Mongo (or local) contains thousands of rows entered by
brokers — much better signal. This script reads those rows, filters to the
5 trained species, fits a GradientBoostingRegressor with grid search, and
writes app/models/price/price_model.joblib.

Feature contract MUST match estimator.py:estimate_price exactly:
    [species_index, weight_kg]
where species_index = fish_species.classIndex (0..4 in the current seed).

Output:
    app/models/price/price_model.joblib

Usage (run with the venv's Python):
    cd profit_sharing_api_fastapi
    PYTHONPATH=. ./venv/Scripts/python.exe scripts/train_price_from_fish_sales.py

    # Preview without writing the model file:
    PYTHONPATH=. ./venv/Scripts/python.exe \
      scripts/train_price_from_fish_sales.py --dry-run

    # Tighter price filter (drop entries with pricePerKg outside [a, b]):
    PYTHONPATH=. ./venv/Scripts/python.exe \
      scripts/train_price_from_fish_sales.py --min-price 30 --max-price 1500

The script reads MONGODB_URI from the .env file. To train against prod:
point .env (or `export MONGODB_URI=...`) at prod, run, then revert.
"""

from __future__ import annotations

import argparse
import asyncio
import math
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from dotenv import load_dotenv
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import GridSearchCV, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

_project_root = Path(__file__).resolve().parents[1]
load_dotenv(_project_root / ".env")

from app.db import connect_db, disconnect_db, get_db  # noqa: E402

OUTPUT_PATH = _project_root / "app" / "models" / "price" / "price_model.joblib"


def _safe_float(value):
    if value is None or value == "":
        return None
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


async def _load_species_index() -> dict[str, int]:
    """Read fish_species → {name: classIndex}. Lowercased keys for matching."""
    db = get_db()
    index: dict[str, int] = {}
    async for sp in db["fish_species"].find({"isActive": True}):
        ci = sp.get("classIndex")
        if ci is None:
            continue
        for key in (sp.get("name"), sp.get("scientificName"), sp.get("englishName")):
            if isinstance(key, str) and key.strip():
                index[key.strip().lower()] = int(ci)
        # Also index the local-name variants split on /
        local = sp.get("localName") or ""
        for part in local.split("/"):
            part = part.strip().lower()
            if part:
                index[part] = int(ci)
    return index


async def _gather_rows(
    species_index: dict[str, int],
    *,
    min_price: float,
    max_price: float,
) -> list[tuple[int, float, float, str]]:
    """Walk fish_sales and emit (classIndex, weightKg, pricePerKg, speciesName).

    Both top-level fish_sales fields (legacy) and embedded lineItems are
    inspected. Only rows that resolve to one of the 5 trained species are kept.
    """
    db = get_db()
    rows: list[tuple[int, float, float, str]] = []
    skipped_unknown_species: Counter = Counter()
    skipped_bad_numeric = 0

    async for sale in db["fish_sales"].find({}):
        candidates: list[dict] = []
        # Legacy single-row sale
        candidates.append(
            {
                "species": sale.get("species"),
                "weightKg": sale.get("weightKg") or sale.get("totalKg"),
                "pricePerKg": sale.get("pricePerKg"),
            }
        )
        # Modern: embedded lineItems
        for li in sale.get("lineItems") or []:
            candidates.append(
                {
                    "species": li.get("species"),
                    "weightKg": li.get("weightKg") or li.get("totalKg"),
                    "pricePerKg": li.get("pricePerKg"),
                }
            )

        for c in candidates:
            species_name = (c.get("species") or "").strip()
            if not species_name:
                continue
            idx = species_index.get(species_name.lower())
            if idx is None:
                skipped_unknown_species[species_name] += 1
                continue
            w = _safe_float(c.get("weightKg"))
            p = _safe_float(c.get("pricePerKg"))
            if w is None or p is None or w <= 0 or p <= 0:
                skipped_bad_numeric += 1
                continue
            if not (min_price <= p <= max_price):
                skipped_bad_numeric += 1
                continue
            rows.append((idx, w, p, species_name))

    if skipped_unknown_species:
        print()
        print("  Skipped species not in current fish_species seed (top 10):")
        for name, n in skipped_unknown_species.most_common(10):
            print(f"    {name:30s} → {n} row(s)")
    if skipped_bad_numeric:
        print(f"  Skipped {skipped_bad_numeric} row(s) with bad/missing weight or price")

    return rows


def _train(
    rows: list[tuple[int, float, float, str]],
    *,
    dry_run: bool,
) -> None:
    if len(rows) < 10:
        raise SystemExit(
            f"Only {len(rows)} usable training rows. Need at least 10. "
            "Either price field on fish_sales is sparse, or species don't "
            "match the current fish_species seed."
        )

    X = np.array([[r[0], r[1]] for r in rows], dtype=float)
    y = np.array([r[2] for r in rows], dtype=float)

    print()
    print("=" * 64)
    print(f"  TRAINING — {len(rows)} usable rows")
    print("=" * 64)

    # Distribution by species
    by_species: Counter = Counter(r[3] for r in rows)
    print()
    print("  By species:")
    for name, n in sorted(by_species.items(), key=lambda t: -t[1]):
        prices = [r[2] for r in rows if r[3] == name]
        weights = [r[1] for r in rows if r[3] == name]
        print(
            f"    {name:25s} n={n:5d}  "
            f"price PHP {min(prices):.0f}–{max(prices):.0f} "
            f"(mean {np.mean(prices):.0f})  "
            f"weight kg {min(weights):.1f}–{max(weights):.1f}"
        )

    cv_folds = min(5, len(X))
    if len(X) >= 50:
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
        cv_score = grid.best_score_
        print()
        print(f"  Best params: {grid.best_params_}")
        print(f"  CV R² (5-fold): {cv_score:.3f}")
    else:
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("regressor", GradientBoostingRegressor(
                n_estimators=200, max_depth=4, learning_rate=0.1, random_state=42
            )),
        ])
        if cv_folds >= 2:
            scores = cross_val_score(model, X, y, cv=cv_folds, scoring="r2")
            print(f"  CV R² ({cv_folds}-fold): {scores.mean():.3f} (±{scores.std():.3f})")
        model.fit(X, y)

    # Honest in-fold sanity check
    y_pred = model.predict(X)
    abs_err = np.abs(y_pred - y)
    pct_err = abs_err / np.maximum(y, 1e-6)
    print(
        f"  Training-set MAE: {abs_err.mean():.1f} PHP/kg, "
        f"MAPE: {pct_err.mean():.1%}"
    )

    if dry_run:
        print()
        print("  --dry-run: not writing model file.")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, OUTPUT_PATH)
    print()
    print(f"  Wrote: {OUTPUT_PATH}")
    print(f"  Size:  {OUTPUT_PATH.stat().st_size:,} bytes")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train price model from fish_sales.lineItems."
    )
    parser.add_argument("--dry-run", action="store_true",
                       help="Train + report metrics but don't write the file.")
    parser.add_argument("--min-price", type=float, default=10.0,
                       help="Drop rows with pricePerKg below this (default: 10).")
    parser.add_argument("--max-price", type=float, default=2000.0,
                       help="Drop rows with pricePerKg above this (default: 2000).")
    args = parser.parse_args()

    print("=" * 64)
    print("  TRAIN PRICE MODEL FROM fish_sales")
    print("=" * 64)
    await connect_db()
    try:
        species_index = await _load_species_index()
        if not species_index:
            raise SystemExit(
                "fish_species collection is empty — re-seed before training."
            )
        print(f"  fish_species classes: {sorted(set(species_index.values()))}")

        rows = await _gather_rows(
            species_index,
            min_price=args.min_price,
            max_price=args.max_price,
        )
        _train(rows, dry_run=args.dry_run)
    finally:
        await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
