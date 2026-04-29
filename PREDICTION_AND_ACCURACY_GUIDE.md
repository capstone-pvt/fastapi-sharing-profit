# Prediction & Accuracy Guide

How to (1) re-import the dataset, (2) train the species classifier and weight
regressor, (3) make a single prediction, and (4) measure accuracy — split
between the **Individual** and **Tub** sheets of the Excel ground-truth file.

All commands assume you are inside the API directory:

```bash
cd profit_sharing_api_fastapi
```

The venv lives at `venv/`. Always use `./venv/Scripts/python.exe` (Windows)
so you don't pick up a different Python on PATH. For YOLO's `yolo` CLI to
resolve, prepend the venv's `Scripts/` to `PATH`:

```bash
PATH="$(pwd)/venv/Scripts:$PATH"
```

Make sure MongoDB is running locally (`mongodb://localhost:27017/smart_catch`)
before any of the DB-touching scripts.

---

## 1. Reset everything and re-import

Wipes the species catalog, the training-samples collection, and backs up the
current model artifacts to `app/models/.backup_<timestamp>/`.

```bash
PYTHONPATH=. ./venv/Scripts/python.exe scripts/clear_training_data.py
```

Then load the dataset folder + Excel ground-truth weights into Mongo:

```bash
PYTHONPATH=. ./venv/Scripts/python.exe scripts/import_dataset_folder.py
```

What this does:
- Inserts 5 `fish_species` docs (one per `dataset/<scientific name>/` folder,
  `classIndex` = 0..4 in alpha order).
- Inserts ~1,015 `fish_training_samples` (one per `.jpg`, species only — no
  weight). `imagePath` points at the dataset folder so no copy is made.
- Inserts 55 extra samples for the Excel ground-truth rows (36 Individual +
  19 Tub) with `weightKg`, `lengthCm`, `widthCm` populated, each round-robin
  attached to a real image in the same species folder.

After this you should see:
```
fish_species count:           5
fish_training_samples count:  1070
   with weightKg > 0:          55
```

---

## 2. Train both models

`auto_train.py` exports the samples, builds the YOLO classification dataset,
trains the YOLOv8 classifier, then trains the scikit-learn weight regressor.
Detection is skipped because no bbox labels were imported.

```bash
PATH="$(pwd)/venv/Scripts:$PATH" PYTHONPATH=. \
  ./venv/Scripts/python.exe scripts/auto_train.py \
    --skip-detect --epochs-classify 25 --imgsz 224
```

Useful flags:
- `--imgsz 224` — small input size, much faster on CPU.
- `--epochs-classify 25` — override the auto-selected epoch count.
- `--model-classify yolov8n-cls.pt` — force the smallest variant if 1k images
  trains too slowly with the auto-selected `yolov8m-cls.pt`.
- `--patience 10` — early stop if no improvement for 10 epochs.
- `--cleanup` — delete `runs/`, `exports/`, `datasets/` after training.

After it finishes you should have:
- `app/models/classifier/best.pt` — YOLOv8 species classifier
- `app/models/weight/weight_model.joblib` — sklearn weight regressor

### Resuming an interrupted run

If the machine slept or training was killed mid-epoch, `runs/classify/trainN/`
still has `weights/last.pt`. Resume from it without rebuilding the dataset:

```bash
PATH="$(pwd)/venv/Scripts:$PATH" \
  yolo classify train resume model=runs/classify/train2/weights/last.pt
```

Then copy the new best weight into `app/models/`:

```bash
cp runs/classify/train2/weights/best.pt app/models/classifier/best.pt
```

Then retrain regression on the latest export:

```bash
LATEST=$(ls -td exports/fish-training/*/ | head -1)
PYTHONPATH=. ./venv/Scripts/python.exe scripts/train_regression_models.py \
  --export-root "$LATEST"
```

---

## 3. Make a single prediction

Two paths: the FastAPI endpoint (production-style) or the Python helpers
directly (debugging).

### 3a. Via the API

```bash
PATH="$(pwd)/venv/Scripts:$PATH" PYTHONPATH=. \
  ./venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

Then `POST /fish/analyze` with a multipart `image` file. The response includes
predicted species, confidence, and estimated weight (kg).

### 3b. Direct Python (no server)

```python
from PIL import Image, ImageEnhance, ImageOps
from ultralytics import YOLO
import joblib, numpy as np

# --- species classifier ---
clf = YOLO("app/models/classifier/best.pt")

img = Image.open("path/to/fish.jpg").convert("RGB")
img = ImageOps.exif_transpose(img) or img
img = ImageEnhance.Sharpness(img).enhance(1.3)
img = ImageEnhance.Contrast(img).enhance(1.1)

result = clf.predict(img, verbose=False)[0]
probs = result.probs.data.cpu().numpy()
top_idx = int(np.argmax(probs))
species_name = result.names[top_idx]
species_confidence = float(probs[top_idx])
print(f"Species: {species_name} ({species_confidence:.1%})")

# --- weight regressor (9 features: 6 base + 3 engineered) ---
weight_model = joblib.load("app/models/weight/weight_model.joblib")

species_index = top_idx          # classIndex from classifier
bbox_w = 0.0                     # px — fill if you have a detector bbox
bbox_h = 0.0                     # px
scale_ref_cm = 0.0               # cm — fill if you have a scale reference (coin)
length_cm = 100.0                # cm — measured fish length
width_cm = 46.0                  # cm — measured fish girth/width

base = np.array([[species_index, bbox_w, bbox_h, scale_ref_cm,
                  length_cm, width_cm]], dtype=float)

# Engineered features (must match scripts/train_regression_models.py)
area = (base[:, 1] * base[:, 2]).reshape(-1, 1)
aspect = np.where(base[:, 2] > 0,
                  base[:, 1] / np.maximum(base[:, 2], 1.0), 1.0).reshape(-1, 1)
area_cm = (base[:, 4] * base[:, 5]).reshape(-1, 1)
features = np.hstack([base, area, aspect, area_cm])

pred_kg = float(weight_model.predict(features)[0])
print(f"Weight: {pred_kg:.2f} kg")
```

If `bbox_w/h/scale_ref_cm` are unknown for your sample, leave them as 0 — the
regressor that ships with this dataset was trained with those columns set to
0 because the Excel rows have no bbox.

---

## 4. Measuring accuracy

There are three things you can measure, each with a separate script:

### 4a. Species classifier (val split)

`auto_train.py` already split 20% of images into `datasets/fish_species/val/`.
Evaluate the classifier on that split:

```bash
PYTHONPATH=. ./venv/Scripts/python.exe scripts/evaluate_models.py \
  --val-dir datasets/fish_species/val \
  --classifier-model app/models/classifier/best.pt
```

Reports overall top-1 / top-5 accuracy, per-class accuracy, and the most
common misclassifications. The val/ folder contains images that were **not**
seen during training, so this is an honest generalization metric.

Add `--min-accuracy 0.90` to make it exit non-zero if accuracy falls below the
threshold (handy for CI gates).

### 4b. Combined classifier + weight regression on Excel ground truth

`scripts/evaluate_dataset_accuracy.py` evaluates the classifier on the val
split AND the weight regressor on the **Individual** and **Tub** sheets of
`dataset/Fish Weight Estimation Dataset.xlsx`, reporting them separately.

```bash
PYTHONPATH=. ./venv/Scripts/python.exe scripts/evaluate_dataset_accuracy.py
```

Output is split into three sections:

#### Individual sheet (per-fish length × girth → weight)
For each row in the `Individual` sheet, the script feeds
`[species_index, 0, 0, 0, fish_length_cm, fish_grid_cm]` (+ engineered
features) into the regressor and compares the predicted kg to the
`actual_weight(kilos)` column.

Reported metrics:
- **MAE (kg)** — mean absolute error in kilograms
- **RMSE (kg)** — root mean squared error
- **MAPE (%)** — mean absolute percentage error
- **R²** — coefficient of determination (1.0 = perfect, 0 = no better than
  predicting the mean)
- **Within ±10% / ±20%** — fraction of rows within that error band
- Per-species breakdown
- Worst 5 predictions

#### Tub sheet (tub L × W → total weight inside)
Same metrics as above, using `tub_length(cm)` as `lengthCm` and
`tub_width(cm)` as `widthCm` from the `Tub` sheet.

#### Species classification
Same numbers as `evaluate_models.py` produces (top-1 accuracy, per-class,
misclassifications). Included so you have one command for both models.

### 4c. Cross-validation R² during training

`scripts/train_regression_models.py` already runs 5-fold CV when training
the weight model and prints the result, e.g.:

```
Weight model GBR CV R²: 0.42 (best params: ...)
Weight model RF  CV R²: 0.31 (...)
```

This is the **honest** generalization signal for the regressor — it splits
the 55 rows into 5 folds and predicts each held-out fold from the other four.
A negative R² here means the model is worse than predicting the mean, which
is your cue to add more training rows or better features (bbox, scale ref).

---

## 5. How to read the Tub vs Individual numbers

The two sheets measure fundamentally different things:

| Sheet      | length_cm input          | width_cm input        | weight target           |
| ---------- | ------------------------ | --------------------- | ----------------------- |
| Individual | length of one fish       | girth of one fish     | weight of that one fish |
| Tub        | length of the tub        | width of the tub      | total fish in the tub   |

That has two consequences when interpreting accuracy:

1. **Same model, two regimes.** The regressor sees both regimes mixed in
   training. It learns something like "if length is in cm-of-fish range, use
   the fish formula; if length is in cm-of-tub range, use the tub formula."
   That's why Individual usually scores much better than Tub — the per-fish
   regime has a clean physical relationship (length × girth ≈ weight), while
   the tub regime has many fish per row with identical container dimensions.

2. **Tub rows have collisions.** All 14 `Karaw` Tub rows share L=49 / W=33,
   yet weights span 24.5–42 kg. The model literally cannot tell those rows
   apart from features alone — it predicts their mean. To improve Tub
   accuracy you need a per-photo signal (fish count, fill height, coin
   scale reference). Until then, expect MAPE ≈ 10–15% and R² near zero on
   that sheet.

So when comparing accuracy across sheets, always look at:
- **Individual** for "is the per-fish weight model good?"
- **Tub** for "can we estimate a tub's load from its outer dimensions alone?"
  (currently: only roughly — within ±20% most of the time)
- **CV R² from training** for the unbiased generalization number that
  doesn't depend on which sheet you tested.

---

## 6. Quick reference

| Task                                | Command                                                                            |
| ----------------------------------- | ---------------------------------------------------------------------------------- |
| Reset DB + model artifacts          | `PYTHONPATH=. python scripts/clear_training_data.py`                               |
| Re-import images + Excel weights    | `PYTHONPATH=. python scripts/import_dataset_folder.py`                             |
| Train classifier + regressor        | `PYTHONPATH=. python scripts/auto_train.py --skip-detect --epochs-classify 25`     |
| Resume interrupted YOLO training    | `yolo classify train resume model=runs/classify/<run>/weights/last.pt`             |
| Train regressor only                | `PYTHONPATH=. python scripts/train_regression_models.py --export-root <dir>`       |
| Classifier accuracy (val split)     | `PYTHONPATH=. python scripts/evaluate_models.py --val-dir datasets/fish_species/val` |
| Full eval (classifier + Tub + Individual) | `PYTHONPATH=. python scripts/evaluate_dataset_accuracy.py`                  |

All long-running scripts can be safely re-run; they overwrite the matching
artifacts (`app/models/classifier/best.pt`, `app/models/weight/weight_model.joblib`).
