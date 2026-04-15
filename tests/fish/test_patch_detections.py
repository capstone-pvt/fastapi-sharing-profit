"""Integration tests for PATCH /fish/analyses/{id}/detections.

Uses client + auth_headers fixtures (from tests/fish/conftest.py and
tests/conftest.py), seeding an analysis via POST /fish/analyze with
monkeypatched ML calls, then exercising the PATCH endpoint.
"""
from __future__ import annotations

import io
import pytest
from PIL import Image

pytestmark = pytest.mark.usefixtures("client")


def _jpg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _seed_analysis(client, auth_headers, monkeypatch):
    from app.api.v1.fish import routes as fish_routes
    from tests.fish.helpers.synthetic_images import make_noise_image

    canned = [
        {
            "id": "det_0",
            "species": "Galunggong",
            "confidence": 0.9,
            "boundingBox": {"x": 0, "y": 0, "width": 100, "height": 50},
        },
        {
            "id": "det_1",
            "species": "Tilapia",
            "confidence": 0.8,
            "boundingBox": {"x": 150, "y": 0, "width": 120, "height": 60},
        },
    ]
    monkeypatch.setattr(fish_routes, "detect_fish", lambda *a, **kw: canned)
    monkeypatch.setattr(
        fish_routes,
        "verify_detections_with_classifier",
        lambda img, dets: dets,
    )
    resp = client.post(
        "/api/fish/analyze?mode=bulk",
        files={"image": ("t.jpg", _jpg(make_noise_image(seed=10)), "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_patch_remove_detection(client, auth_headers, monkeypatch):
    aid = _seed_analysis(client, auth_headers, monkeypatch)
    resp = client.patch(
        f"/api/fish/analyses/{aid}/detections",
        json={"remove": ["det_0"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["detections"]) == 1
    assert body["detections"][0]["id"] == "det_1"


def test_patch_update_species(client, auth_headers, monkeypatch):
    aid = _seed_analysis(client, auth_headers, monkeypatch)
    resp = client.patch(
        f"/api/fish/analyses/{aid}/detections",
        json={"update": [{"id": "det_0", "species": "Bangus"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    species = {d["id"]: d["species"] for d in resp.json()["detections"]}
    assert species["det_0"] == "Bangus"


def test_patch_add_detection_recomputes_totals(client, auth_headers, monkeypatch):
    aid = _seed_analysis(client, auth_headers, monkeypatch)
    resp = client.patch(
        f"/api/fish/analyses/{aid}/detections",
        json={
            "add": [
                {
                    "species": "Bangus",
                    "estimatedWeight": 0.4,
                    "confidence": 0.9,
                    "boundingBox": {"x": 300, "y": 0, "width": 100, "height": 50},
                }
            ]
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["detections"]) == 3


def test_patch_nonexistent_404(client, auth_headers):
    resp = client.patch(
        "/api/fish/analyses/000000000000000000000000/detections",
        json={"remove": ["det_0"]},
        headers=auth_headers,
    )
    assert resp.status_code == 404
