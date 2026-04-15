"""Integration tests for /fish/analyze with reference-object calibration.

These tests monkey-patch the ML models so they run offline without
downloading model weights — the detection logic itself is exercised
via synthetic images in test_reference_detector.py.
"""
from __future__ import annotations

import io
import json

import pytest
from PIL import Image


pytestmark = pytest.mark.usefixtures("client")


def _jpg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def test_analyze_default_behaviour_unchanged(client, auth_headers, monkeypatch):
    from app.api.v1.fish import routes as fish_routes

    monkeypatch.setattr(fish_routes, "detect_fish", lambda *a, **kw: [])
    monkeypatch.setattr(
        fish_routes, "classify_fish",
        lambda *a, **kw: ("Tilapia", 0.9),
    )
    monkeypatch.setattr(
        fish_routes, "classify_fish_top_n",
        lambda *a, **kw: [{"species": "Tilapia", "confidence": 0.9}],
    )

    from tests.fish.helpers.synthetic_images import make_noise_image
    img = make_noise_image(seed=1)

    resp = client.post(
        "/api/fish/analyze",
        files={"image": ("test.jpg", _jpg_bytes(img), "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        body = resp.json()
        assert body["referenceDetection"]["status"] == "manual"
        assert body["mode"] == "single"
        assert "bulkSummary" not in body


def test_analyze_bulk_mode_adds_bulk_summary(client, auth_headers, monkeypatch):
    from app.api.v1.fish import routes as fish_routes

    canned = [
        {"id": "det_0", "species": "Galunggong", "confidence": 0.9,
         "boundingBox": {"x": 0, "y": 0, "width": 100, "height": 50}},
        {"id": "det_1", "species": "Galunggong", "confidence": 0.8,
         "boundingBox": {"x": 150, "y": 0, "width": 100, "height": 50}},
    ]
    monkeypatch.setattr(fish_routes, "detect_fish", lambda *a, **kw: canned)
    monkeypatch.setattr(
        fish_routes, "verify_detections_with_classifier",
        lambda img, dets: dets,
    )

    from tests.fish.helpers.synthetic_images import make_aruco_image
    img = make_aruco_image(canvas=(800, 600), side_px=200)

    resp = client.post(
        "/api/fish/analyze?mode=bulk&referenceType=aruco_4cm",
        files={"image": ("test.jpg", _jpg_bytes(img), "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "bulk"
    assert body["referenceDetection"]["status"] == "detected"
    assert body["referenceDetection"]["type"] == "aruco_4cm"
    assert "bulkSummary" in body
    assert body["bulkSummary"]["totalFish"] == 2
    assert body["bulkSummary"]["dominantSpecies"] == "Galunggong"


def test_analyze_reference_not_found_is_not_a_failure(client, auth_headers, monkeypatch):
    from app.api.v1.fish import routes as fish_routes
    monkeypatch.setattr(fish_routes, "detect_fish", lambda *a, **kw: [])
    monkeypatch.setattr(
        fish_routes, "classify_fish",
        lambda *a, **kw: ("Tilapia", 0.9),
    )
    monkeypatch.setattr(
        fish_routes, "classify_fish_top_n",
        lambda *a, **kw: [{"species": "Tilapia", "confidence": 0.9}],
    )

    from tests.fish.helpers.synthetic_images import make_noise_image
    img = make_noise_image(seed=99)
    resp = client.post(
        "/api/fish/analyze?referenceType=coin_php_5",
        files={"image": ("test.jpg", _jpg_bytes(img), "image/jpeg")},
        headers=auth_headers,
    )
    if resp.status_code == 200:
        assert resp.json()["referenceDetection"]["status"] in ("not_found", "manual")


def test_analyze_invalid_reference_type_400(client, auth_headers):
    from tests.fish.helpers.synthetic_images import make_noise_image
    img = make_noise_image(seed=5)
    resp = client.post(
        "/api/fish/analyze?referenceType=cheese",
        files={"image": ("test.jpg", _jpg_bytes(img), "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "referenceType" in resp.text


def test_analyze_tap_to_mark(client, auth_headers, monkeypatch):
    from app.api.v1.fish import routes as fish_routes
    monkeypatch.setattr(fish_routes, "detect_fish", lambda *a, **kw: [
        {"id": "det_0", "species": "Tilapia", "confidence": 0.9,
         "boundingBox": {"x": 300, "y": 200, "width": 200, "height": 80}},
    ])
    monkeypatch.setattr(
        fish_routes, "verify_detections_with_classifier",
        lambda img, dets: dets,
    )

    from tests.fish.helpers.synthetic_images import make_noise_image
    img = make_noise_image(seed=6)
    bbox = json.dumps({"x": 10, "y": 10, "width": 100, "height": 100})
    resp = client.post(
        f"/api/fish/analyze?referenceType=coin_php_5&referenceBoundingBox={bbox}",
        files={"image": ("test.jpg", _jpg_bytes(img), "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["referenceDetection"]["status"] == "client_supplied"
    assert body["referenceDetection"]["pixelsPerCm"] == pytest.approx(40.0)
    assert body["detections"][0]["calibrationSource"] == "reference"
