# ML Models Directory

This directory contains the machine learning models used for fish image analysis.

## Required Models

### 1. Fish Detector Model (YOLO)
**Location:** `detector/best.pt`
**Type:** YOLOv8 object detection model
**Purpose:** Detects and localizes fish in images with bounding boxes
**Format:** PyTorch (.pt file)

**Training:** Train a YOLOv8 detection model on fish images with bounding box annotations.

```bash
# Example using ultralytics
pip install ultralytics
yolo detect train data=fish_dataset.yaml model=yolov8n.pt epochs=100
```

---

### 2. Fish Classifier Model (YOLO)
**Location:** `classifier/best.pt`
**Type:** YOLOv8 classification model
**Purpose:** Classifies fish species when detector doesn't find specific fish
**Format:** PyTorch (.pt file)

**Training:** Train a YOLOv8 classification model on labeled fish species images.

```bash
# Example using ultralytics
yolo classify train data=fish_species_folder model=yolov8n-cls.pt epochs=100
```

---

### 3. Weight Estimation Model
**Location:** `weight/weight_model.joblib`
**Type:** Scikit-learn regression model
**Purpose:** Estimates fish weight based on dimensions and species
**Format:** Joblib pickle file

**Features Expected:**
- species_index (int)
- bbox_width (float - pixels)
- bbox_height (float - pixels)
- scale_reference_cm (float)
- length_cm (float)
- width_cm (float)

**Training Example:**
```python
from sklearn.ensemble import RandomForestRegressor
import joblib

# Train on fish measurement data
model = RandomForestRegressor()
model.fit(X_train, y_train_weight)

# Save model
joblib.dump(model, 'models/weight/weight_model.joblib')
```

---

### 4. Price Prediction Model
**Location:** `price/price_model.joblib`
**Type:** Scikit-learn regression model
**Purpose:** Predicts fish price based on species and weight
**Format:** Joblib pickle file

**Features Expected:**
- species_index (int)
- estimated_weight (float - kg)

**Output:** Price per kg (float)

**Training Example:**
```python
from sklearn.linear_model import LinearRegression
import joblib

# Train on historical fish pricing data
model = LinearRegression()
model.fit(X_train, y_train_price_per_kg)

# Save model
joblib.dump(model, 'models/price/price_model.joblib')
```

---

## Model Setup Options

### Option 1: Use Pre-trained Models (Recommended if available)
If you have pre-trained models, place them in the respective directories:
- `detector/best.pt`
- `classifier/best.pt`
- `weight/weight_model.joblib`
- `price/price_model.joblib`

### Option 2: Train Your Own Models
1. Collect and label training data for fish species in your region
2. Train YOLO models for detection and classification
3. Train regression models for weight and price estimation
4. Place trained models in the correct directories

### Option 3: Use Placeholder/Demo Models
For testing without real models, you can:
1. Use YOLOv8 base models (download from Ultralytics)
2. Create simple regression models with dummy data
3. The system will fall back to basic estimation algorithms

### Option 4: Disable ML Features (Temporary)
To run the app without ML models:
1. Clear the model paths in `.env`:
   ```
   CLASSIFIER_MODEL_PATH=
   DETECTOR_MODEL_PATH=
   WEIGHT_MODEL_PATH=
   PRICE_MODEL_PATH=
   ```
2. The system will use fallback logic:
   - Manual classification
   - Simple area-based weight estimation (width * height * 0.000001)
   - Default price estimation ($8.50/kg)

---

## Verification

After placing models, start the API server and check the logs:

```bash
uvicorn app.main:app --reload
```

You should see:
```
SUCCESS: Detector model loaded from models/detector/best.pt
SUCCESS: Classifier model loaded from models/classifier/best.pt
SUCCESS: Weight model loaded from models/weight/weight_model.joblib
SUCCESS: Price model loaded from models/price/price_model.joblib
```

If models are missing, you'll see:
```
ERROR: Detector model file not found at: models/detector/best.pt
```

---

## Environment Configuration

Models are configured in `.env` file:

```env
# ML Model Paths
CLASSIFIER_MODEL_PATH=models/classifier/best.pt
DETECTOR_MODEL_PATH=models/detector/best.pt
WEIGHT_MODEL_PATH=models/weight/weight_model.joblib
PRICE_MODEL_PATH=models/price/price_model.joblib

# Detection Parameters
DETECTOR_CONFIDENCE=0.25  # Minimum confidence threshold (0.0-1.0)
DETECTOR_IOU=0.45         # Intersection over Union threshold for NMS

# Size Classification Thresholds
SIZE_SMALL_MAX_KG=0.5     # Max weight for "Small" fish
SIZE_MEDIUM_MAX_KG=1.5    # Max weight for "Medium" fish
```

---

## Dependencies

Ensure these packages are installed:

```bash
pip install ultralytics  # For YOLO models
pip install torch        # PyTorch backend for YOLO
pip install joblib       # For loading .joblib models
pip install scikit-learn # For regression models
pip install numpy        # For numerical operations
pip install Pillow       # For image processing
```

---

## Troubleshooting

### "Fish analysis service unavailable" Error
- **Cause:** ML models not found or failed to load
- **Solution:** Check that all 4 model files exist in correct locations
- **Logs:** Check server console for ERROR messages about missing files

### "No fish detected" Error
- **Cause:** Model can't find fish in the image, or confidence too low
- **Solution:**
  - Try adjusting DETECTOR_CONFIDENCE (lower = more detections)
  - Ensure image has clear, visible fish
  - Verify detector model is trained on similar fish species

### Models Load but Analysis Fails
- **Cause:** Model format mismatch or incorrect input features
- **Solution:**
  - Verify YOLO models are YOLOv8 format (.pt files)
  - Verify joblib models match expected input features
  - Check model training data matches production species

---

## Support

For model training assistance or pre-trained models, contact your ML team or refer to:
- Ultralytics YOLO documentation: https://docs.ultralytics.com/
- Scikit-learn documentation: https://scikit-learn.org/
