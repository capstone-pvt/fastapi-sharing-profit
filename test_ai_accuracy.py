"""
AI Scan Accuracy Test
Tests the fish detection, classification, weight estimation, and price prediction pipeline
using real uploaded images from the uploads directory.
"""
import json
import os
import sys
import time
from pathlib import Path

import httpx

BASE = "http://localhost:8000/api"

# Login
client = httpx.Client(base_url=BASE, timeout=120.0)
r = client.post("/auth/login", json={"email": "super@demo.com", "password": "P@ssw0rd123"})
if r.status_code != 200:
    print("ERROR: Cannot login")
    sys.exit(1)
token = r.json()["accessToken"]
headers = {"Authorization": f"Bearer {token}"}

# ─── 1. MODEL DIAGNOSTIC ─────────────────────
print("=" * 70)
print("  1. MODEL DIAGNOSTIC")
print("=" * 70)

r = client.get("/fish/diagnostic", headers=headers)
diag = r.json()
for model_name, info in diag.get("models", {}).items():
    status = "LOADED" if info.get("exists") else "MISSING"
    print(f"  [{status}] {model_name}: {info.get('path', 'N/A')}")
print(f"  Species in DB: {diag.get('species', {}).get('count', 0)}")

# ─── 2. CLASSIFIER MODEL INFO ────────────────
print("\n" + "=" * 70)
print("  2. YOLO MODEL CLASS NAMES")
print("=" * 70)

# Check classifier class names
try:
    from ultralytics import YOLO
    classifier_path = "app/models/classifier/best.pt"
    detector_path = "app/models/detector/best.pt"

    if os.path.exists(classifier_path):
        cls_model = YOLO(classifier_path)
        cls_names = cls_model.names
        print(f"  Classifier classes: {len(cls_names)}")
        for idx, name in sorted(cls_names.items()):
            print(f"    [{idx:2d}] {name}")

    if os.path.exists(detector_path):
        det_model = YOLO(detector_path)
        det_names = det_model.names
        print(f"\n  Detector classes: {len(det_names)}")
        for idx, name in sorted(det_names.items()):
            print(f"    [{idx:2d}] {name}")
except ImportError:
    print("  [SKIP] ultralytics not available for direct model inspection")

# ─── 3. SCAN REAL IMAGES ─────────────────────
print("\n" + "=" * 70)
print("  3. AI SCAN - REAL UPLOADED IMAGES")
print("=" * 70)

uploads_dir = Path("uploads/fish")
if not uploads_dir.exists():
    print(f"  No uploads directory found at {uploads_dir}")
    sys.exit(1)

# Get all image files
image_files = sorted([
    f for f in uploads_dir.iterdir()
    if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
])

print(f"  Found {len(image_files)} images in {uploads_dir}\n")

total_scans = 0
total_detections = 0
total_errors = 0
species_counts = {}
confidence_sum = 0
confidence_count = 0
weight_values = []
price_values = []
scan_times = []
zero_detection_files = []

# Test each image (limit to 20 for speed)
test_images = image_files[:20]

for img_path in test_images:
    total_scans += 1
    print(f"  [{total_scans:2d}] {img_path.name}...", end=" ", flush=True)

    start = time.time()
    try:
        with open(img_path, "rb") as f:
            content_type = "image/jpeg" if img_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
            r = client.post(
                "/fish/analyze",
                headers={"Authorization": f"Bearer {token}"},
                files={"image": (img_path.name, f, content_type)},
                data={"singleFish": "false", "confidence": "0.25", "iou": "0.45"},
            )
        elapsed = time.time() - start
        scan_times.append(elapsed)

        if r.status_code != 200:
            print(f"ERROR {r.status_code}: {r.text[:100]}")
            total_errors += 1
            continue

        result = r.json()
        detections = result.get("detections", [])
        num_det = len(detections)
        total_detections += num_det

        if num_det == 0:
            print(f"No detections ({elapsed:.1f}s)")
            zero_detection_files.append(img_path.name)
            continue

        # Collect stats
        det_summaries = []
        for det in detections:
            species = det.get("species", "Unknown")
            conf = det.get("confidence", 0)
            weight = det.get("estimatedWeight", 0)
            size = det.get("sizeCategory", "?")

            species_counts[species] = species_counts.get(species, 0) + 1
            confidence_sum += conf
            confidence_count += 1
            if weight > 0:
                weight_values.append(weight)

            # Check price enrichment
            price_info = det.get("estimatedPricePerKg")
            if price_info:
                price_values.append(price_info)

            det_summaries.append(f"{species}({conf:.0%},{weight:.2f}kg,{size})")

        print(f"{num_det} det | {', '.join(det_summaries)} | {elapsed:.1f}s")

    except Exception as e:
        print(f"EXCEPTION: {e}")
        total_errors += 1

# ─── 4. SINGLE FISH MODE TEST ────────────────
print("\n" + "=" * 70)
print("  4. SINGLE FISH MODE TEST")
print("=" * 70)

if test_images:
    img = test_images[0]
    with open(img, "rb") as f:
        ct = "image/jpeg" if img.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        r = client.post(
            "/fish/analyze",
            headers={"Authorization": f"Bearer {token}"},
            files={"image": (img.name, f, ct)},
            data={"singleFish": "true", "confidence": "0.15"},
        )
    if r.status_code == 200:
        result = r.json()
        dets = result.get("detections", [])
        print(f"  Single fish mode: {len(dets)} detection(s) (should be <= 1)")
        if dets:
            d = dets[0]
            print(f"    Species: {d.get('species')}")
            print(f"    Confidence: {d.get('confidence', 0):.2%}")
            print(f"    Weight: {d.get('estimatedWeight', 0):.3f} kg")
            print(f"    Size: {d.get('sizeCategory')}")
            print(f"    Scientific: {d.get('scientificName', 'N/A')}")
            print(f"    Local: {d.get('localName', 'N/A')}")
            bbox = d.get("boundingBox", {})
            print(f"    BBox: x={bbox.get('x',0):.0f} y={bbox.get('y',0):.0f} w={bbox.get('width',0):.0f} h={bbox.get('height',0):.0f}")
            kp = d.get("keypoints", {})
            if kp:
                print(f"    Keypoints: mouth={kp.get('mouth')}, tail={kp.get('tail')}")
            pr = d.get("estimatedPricePerKg")
            if pr:
                print(f"    Price/kg: P{pr.get('minPhp',0)}-{pr.get('maxPhp',0)} (inSeason: {pr.get('inSeason')})")
    else:
        print(f"  ERROR: {r.status_code}")

# ─── 5. DIFFERENT CONFIDENCE THRESHOLDS ──────
print("\n" + "=" * 70)
print("  5. CONFIDENCE THRESHOLD COMPARISON")
print("=" * 70)

if test_images:
    img = test_images[0]
    for conf_threshold in [0.10, 0.25, 0.50, 0.75]:
        with open(img, "rb") as f:
            ct = "image/jpeg" if img.suffix.lower() in (".jpg", ".jpeg") else "image/png"
            r = client.post(
                "/fish/analyze",
                headers={"Authorization": f"Bearer {token}"},
                files={"image": (img.name, f, ct)},
                data={"singleFish": "false", "confidence": str(conf_threshold)},
            )
        if r.status_code == 200:
            dets = r.json().get("detections", [])
            confs = [d.get("confidence", 0) for d in dets]
            avg_c = sum(confs) / len(confs) if confs else 0
            print(f"  Threshold {conf_threshold:.0%}: {len(dets)} detections, avg conf: {avg_c:.2%}")

# ─── 6. ANALYSIS HISTORY ─────────────────────
print("\n" + "=" * 70)
print("  6. ANALYSIS HISTORY CHECK")
print("=" * 70)

r = client.get("/fish/analysis-history?limit=5", headers=headers)
if r.status_code == 200:
    data = r.json()
    results = data.get("results", [])
    total = data.get("total", 0)
    print(f"  Total analyses in DB: {total}")
    print(f"  Latest 5:")
    for a in results[:5]:
        dets = a.get("detections", [])
        species_list = [d.get("species", "?") for d in dets]
        print(f"    {a.get('createdAt', '?')[:19]} | {len(dets)} det | {', '.join(species_list[:3])}")

# ─── 7. ANALYTICS COUNT ──────────────────────
print("\n" + "=" * 70)
print("  7. FISH ANALYTICS")
print("=" * 70)

r = client.get("/fish/analytics", headers=headers)
if r.status_code == 200:
    analytics = r.json()
    print(f"  {json.dumps(analytics, indent=2, default=str)[:500]}")

# ─── FINAL REPORT ─────────────────────────────
print("\n" + "=" * 70)
print("  AI SCAN ACCURACY REPORT")
print("=" * 70)

avg_conf = (confidence_sum / confidence_count * 100) if confidence_count > 0 else 0
avg_time = sum(scan_times) / len(scan_times) if scan_times else 0
avg_weight = sum(weight_values) / len(weight_values) if weight_values else 0
detection_rate = (total_detections / total_scans * 100) if total_scans > 0 else 0

print(f"""
  Images scanned:      {total_scans}
  Total detections:    {total_detections}
  Detection rate:      {total_detections}/{total_scans} ({detection_rate:.0f}% of images had fish)
  Errors:              {total_errors}
  Zero-detection:      {len(zero_detection_files)}

  Avg confidence:      {avg_conf:.1f}%
  Avg scan time:       {avg_time:.2f}s
  Avg est. weight:     {avg_weight:.3f} kg

  Species detected:    {len(species_counts)}
  Species breakdown:""")

for species, count in sorted(species_counts.items(), key=lambda x: -x[1]):
    print(f"    {species:25s}: {count} detection(s)")

if zero_detection_files:
    print(f"\n  Images with 0 detections:")
    for f in zero_detection_files:
        print(f"    - {f}")

print(f"\n  Price enrichment:    {len(price_values)}/{confidence_count} detections have price data")
print("=" * 70)
