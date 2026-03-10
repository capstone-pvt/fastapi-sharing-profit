# Fish AI Model Training & Prediction Guide

## Overview

The Fish AI Detection system uses four ML models to analyze fish images:

| Model | Type | Framework | Purpose | Path |
|-------|------|-----------|---------|------|
| **Detector** | YOLOv8 Object Detection | Ultralytics | Locates fish in images with bounding boxes | `app/models/detector/best.pt` |
| **Classifier** | YOLOv8 Classification | Ultralytics | Identifies fish species | `app/models/classifier/best.pt` |
| **Weight Estimator** | GradientBoostingRegressor | Scikit-learn | Predicts fish weight from dimensions | `app/models/weight/weight_model.joblib` |
| **Price Predictor** | GradientBoostingRegressor | Scikit-learn | Estimates price per kg | `app/models/price/price_model.joblib` |

---

## Prerequisites

```bash
cd profit_sharing_api_fastapi
pip install -r requirements.txt
```

### Kaggle Setup (one-time)

1. Go to https://www.kaggle.com/settings
2. Click **Create New Token** to download `kaggle.json`
3. Place it in:
   - **Windows:** `%USERPROFILE%\.kaggle\kaggle.json`
   - **Linux/Mac:** `~/.kaggle/kaggle.json`

---

## Training

### Quick Start (Recommended)

Download datasets from Kaggle, train the classifier, and clean up in one command:

```bash
# Download all datasets + train + cleanup
python scripts/download_kaggle_dataset.py --all
PYTHONPATH=. python scripts/auto_train.py \
  --export-root exports/kaggle/merged \
  --skip-detect --skip-regression \
  --cleanup \
  --epochs-classify 20
```

### Step-by-Step Training

#### 1. Download Datasets

```bash
# Download all supported datasets (Large Scale Fish + Philippine Fish)
python scripts/download_kaggle_dataset.py --all

# Or download specific datasets
python scripts/download_kaggle_dataset.py --presets large-scale
python scripts/download_kaggle_dataset.py --presets ph-fish
python scripts/download_kaggle_dataset.py --presets large-scale ph-fish

# Download a single custom dataset
python scripts/download_kaggle_dataset.py --dataset crowww/a-large-scale-fish-dataset

# Limit images per species (faster for testing)
python scripts/download_kaggle_dataset.py --all --max-per-class 200
```

**Available preset datasets:**

| Preset | Kaggle Slug | Species | Images |
|--------|-------------|---------|--------|
| `large-scale` | `crowww/a-large-scale-fish-dataset` | 9 | ~9,430 |
| `ph-fish` | `markdaniellampa/fish-dataset` | 31 | ~13,300 |
| `nature-conservancy` | Competition (requires rule acceptance) | 6 | ~3,777 |

#### 2. Build Classification Dataset

```bash
python scripts/build_classification_dataset.py --export-root exports/kaggle/merged
```

This creates the `datasets/fish_species/` directory with `train/` and `val/` splits organized by species folders.

#### 3. Train the Classifier

```bash
# Using auto_train (recommended)
PYTHONPATH=. python scripts/auto_train.py \
  --export-root exports/kaggle/merged \
  --skip-detect --skip-regression \
  --epochs-classify 20

# Or train directly with YOLO CLI
yolo classify train data=datasets/fish_species model=yolov8n-cls.pt epochs=20
```

#### 4. Train Detection Model (Optional)

Requires YOLO-format bounding box labels in `exports/<dataset>/labels/`:

```bash
python scripts/build_yolo_dataset.py --export-root exports/kaggle/merged
yolo detect train data=fish_dataset.yaml model=yolov8n.pt epochs=20 imgsz=640
```

#### 5. Train Regression Models (Optional)

Requires `weight_data.csv` and `price_data.csv` with actual weight/price data:

```bash
python scripts/train_regression_models.py --export-root exports/kaggle/merged
```

### Auto Train (Full Pipeline)

The `auto_train.py` script handles the entire pipeline:

```bash
PYTHONPATH=. python scripts/auto_train.py \
  --export-root exports/kaggle/merged \
  --epochs-classify 20 \
  --epochs-detect 20 \
  --skip-detect \
  --skip-regression \
  --cleanup
```

**Options:**

| Flag | Description |
|------|-------------|
| `--export-root` | Path to the exported dataset directory |
| `--epochs-classify` | Number of classification training epochs (default: 10) |
| `--epochs-detect` | Number of detection training epochs (default: 10) |
| `--imgsz` | Image size for detection training (default: 640) |
| `--skip-detect` | Skip detection model training |
| `--skip-classify` | Skip classification model training |
| `--skip-regression` | Skip weight/price regression training |
| `--cleanup` | Delete datasets, downloads, exports, and runs after training |

After training, `auto_train.py` automatically:
- Copies the best model weights to `app/models/`
- Saves training metrics to the `fish_models` MongoDB collection
- Cleans up temporary files (if `--cleanup` is used)

### Training Results in Database

Training records are saved to the `fish_models` collection with this structure:

```json
{
  "modelType": "classifier",
  "version": "20260310_090000",
  "modelPath": "app/models/classifier/best.pt",
  "description": "Trained on 22733 images, 40 species, 20 epochs",
  "isActive": true,
  "status": "completed",
  "trainingMetrics": {
    "top1Accuracy": 0.975,
    "top5Accuracy": 0.997,
    "epochs": 20
  },
  "datasetInfo": {
    "totalImages": 22733,
    "speciesCount": 40,
    "speciesNames": ["Bangus", "Catfish", "Tilapia", "..."]
  },
  "trainedAt": "2026-03-10T..."
}
```

---

## Prediction (Using Trained Models)

### API Endpoint

**`POST /fish/analyze`**

Analyzes a fish image and returns species classification, weight estimation, and price prediction.

#### Request

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image` | File | Yes | Fish image (JPEG, PNG) |
| `singleFish` | bool | No | Return only the top detection |
| `scaleReferenceCm` | float | No | Reference scale in cm for size estimation |
| `confidence` | float | No | Min detection confidence (0.0-1.0, default: 0.25) |
| `iou` | float | No | NMS IOU threshold (default: 0.45) |

**Example (cURL):**

```bash
curl -X POST http://localhost:8000/api/v1/fish/analyze \
  -H "Authorization: Bearer <your-token>" \
  -F "image=@fish_photo.jpg" \
  -F "singleFish=true" \
  -F "scaleReferenceCm=10"
```

**Example (Python):**

```python
import httpx

with open("fish_photo.jpg", "rb") as f:
    response = httpx.post(
        "http://localhost:8000/api/v1/fish/analyze",
        headers={"Authorization": "Bearer <your-token>"},
        files={"image": ("fish.jpg", f, "image/jpeg")},
        data={"singleFish": "true", "scaleReferenceCm": "10"},
    )
    result = response.json()
    print(result)
```

#### Response

```json
{
  "imageUrl": "uploads/analysis_1710000000000.jpg",
  "userId": "user123",
  "detections": [
    {
      "id": "det_0",
      "species": "Yellowfin Tuna",
      "confidence": 0.95,
      "boundingBox": {
        "x": 100.0,
        "y": 150.0,
        "width": 200.0,
        "height": 180.0
      },
      "estimatedWeight": 15.5,
      "sizeCategory": "Large",
      "lengthCm": 45.2,
      "widthCm": 38.1,
      "scientificName": "Thunnus albacares",
      "englishName": "Yellowfin Tuna",
      "localName": "Tambakol/Tulingan/Tangi"
    }
  ],
  "totalEstimatedWeight": 15.5,
  "predictedPrice": 260.10,
  "speciesCount": { "Yellowfin Tuna": 1 },
  "analyzedAt": "2026-03-10T09:00:00",
  "singleFish": true,
  "scaleReferenceCm": 10.0,
  "imageWidth": 800,
  "imageHeight": 600,
  "scannedBy": "Juan Dela Cruz"
}
```

### How Prediction Works

```
Image Upload
    |
    v
[1] Fish Detection (YOLOv8 detector)
    |-- Found fish? --> Bounding boxes + species from detector
    |-- No fish?    --> [2] Fallback to Classifier
    |                       |
    |                       v
    |               Species classification (YOLOv8 classifier)
    |
    v
[3] Filter by Active Species (from fish_species DB collection)
    |
    v
[4] Weight Estimation (GradientBoostingRegressor)
    |   Input: species_index, bbox_width, bbox_height, scale_cm, length_cm, width_cm
    |   Fallback: width * height * 0.000001 (if model unavailable)
    |
    v
[5] Price Prediction (GradientBoostingRegressor)
    |   Input: species_index, estimated_weight
    |   Fallback: weight * 8.5 (if model unavailable)
    |
    v
[6] Build Analysis Document --> Save to MongoDB --> Return Response
```

### Other Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/fish/analyze` | POST | Analyze fish image |
| `/fish/analytics` | GET | Get analysis count summary |
| `/fish/analysis-history` | GET | Get user's analysis history |
| `/fish/species` | GET | List all registered species |
| `/fish/species/active` | GET | List active species |
| `/fish/models` | GET | List all trained models |
| `/fish/models/active?model_type=classifier` | GET | Get active model by type |
| `/fish/training-samples` | POST | Upload training sample |
| `/fish/training-samples/export` | GET | Export dataset for training |

---

## Adding New Species

### 1. Register species in the database

Edit `scripts/seed_ph_fish_species.py` to add new species, then run:

```bash
PYTHONPATH=. python scripts/seed_ph_fish_species.py
```

Or use the API:

```bash
curl -X POST http://localhost:8000/api/v1/fish/species \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Yellowfin Tuna",
    "scientificName": "Thunnus albacares",
    "englishName": "Yellowfin Tuna",
    "localName": "Tambakol/Tulingan",
    "genus": "Thunnus",
    "family": "Scombridae",
    "isActive": true
  }'
```

### 2. Collect training images

Upload training samples via the API or add images to a Kaggle-compatible dataset structure.

### 3. Retrain the model

```bash
python scripts/download_kaggle_dataset.py --all
PYTHONPATH=. python scripts/auto_train.py \
  --export-root exports/kaggle/merged \
  --skip-detect --skip-regression \
  --cleanup --epochs-classify 20
```

---

## Model Configuration

All model paths are configured in `.env`:

```env
MODEL_ROOT=app/models
CLASSIFIER_MODEL_PATH=app/models/classifier/best.pt
DETECTOR_MODEL_PATH=app/models/detector/best.pt
WEIGHT_MODEL_PATH=app/models/weight/weight_model.joblib
PRICE_MODEL_PATH=app/models/price/price_model.joblib
DETECTOR_CONFIDENCE=0.25
DETECTOR_IOU=0.45
```

Models are lazy-loaded on first use and cached in memory for subsequent requests.

---

## Disk Space Management

Training datasets can be large (~10-15 GB). The `--cleanup` flag in `auto_train.py` automatically removes temporary files after training:

| Directory | Purpose | Cleaned Up |
|-----------|---------|------------|
| `downloads/` | Raw Kaggle downloads | Yes |
| `exports/` | Prepared training data | Yes |
| `datasets/` | Train/val splits | Yes |
| `runs/` | YOLO training logs & checkpoints | Yes |
| `app/models/` | Final model weights (~10 MB total) | **Kept** |

All temporary directories are also listed in `.gitignore` to prevent accidental commits.
