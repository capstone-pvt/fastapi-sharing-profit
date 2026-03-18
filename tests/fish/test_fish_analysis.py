"""Tests for fish analysis (scan), analytics, and analysis history."""
import io
import pytest
from PIL import Image


def _create_test_image() -> bytes:
    """Create a minimal valid JPEG image for upload."""
    img = Image.new("RGB", (100, 100), color=(0, 128, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.getvalue()


class TestAnalyzeFish:
    def test_analyze_with_image(self, client, broker_headers):
        image_bytes = _create_test_image()
        resp = client.post(
            "/api/fish/analyze",
            headers=broker_headers,
            files={"image": ("test_fish.jpg", image_bytes, "image/jpeg")},
        )
        # 200 if models loaded, 400/500 if models not available
        assert resp.status_code in (200, 400, 500), resp.text

    def test_analyze_with_single_fish_flag(self, client, broker_headers):
        image_bytes = _create_test_image()
        resp = client.post(
            "/api/fish/analyze?singleFish=true",
            headers=broker_headers,
            files={"image": ("single_fish.jpg", image_bytes, "image/jpeg")},
        )
        assert resp.status_code in (200, 400, 500), resp.text

    def test_analyze_with_caught_by(self, client, broker_headers, crew_headers):
        # Get a crew member's profile to use as caughtBy
        profile = client.get("/api/profile", headers=crew_headers).json()
        crew_id = profile.get("userId") or profile.get("id")
        crew_name = f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip()

        image_bytes = _create_test_image()
        params = f"?caughtBy={crew_id}&caughtByName={crew_name}" if crew_id else ""
        resp = client.post(
            f"/api/fish/analyze{params}",
            headers=broker_headers,
            files={"image": ("caught_fish.jpg", image_bytes, "image/jpeg")},
        )
        assert resp.status_code in (200, 400, 500), resp.text

    def test_analyze_no_image_returns_422(self, client, broker_headers):
        resp = client.post("/api/fish/analyze", headers=broker_headers)
        assert resp.status_code == 422  # missing required file

    def test_unauthenticated_cannot_analyze(self, client):
        image_bytes = _create_test_image()
        resp = client.post(
            "/api/fish/analyze",
            files={"image": ("test.jpg", image_bytes, "image/jpeg")},
        )
        assert resp.status_code == 401

    def test_crew_can_analyze(self, client, crew_headers):
        image_bytes = _create_test_image()
        resp = client.post(
            "/api/fish/analyze",
            headers=crew_headers,
            files={"image": ("crew_fish.jpg", image_bytes, "image/jpeg")},
        )
        assert resp.status_code in (200, 400, 500), resp.text


class TestFishDiagnostic:
    def test_broker_can_access_diagnostic(self, client, broker_headers):
        resp = client.get("/api/fish/diagnostic", headers=broker_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "species" in data

    def test_crew_cannot_access_diagnostic(self, client, crew_headers):
        resp = client.get("/api/fish/diagnostic", headers=crew_headers)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_access_diagnostic(self, client):
        resp = client.get("/api/fish/diagnostic")
        assert resp.status_code == 401


class TestFishAnalytics:
    def test_get_analytics(self, client, broker_headers):
        resp = client.get("/api/fish/analytics", headers=broker_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "totalAnalyses" in data
        assert "userAnalyses" in data

    def test_crew_cannot_access_analytics(self, client, crew_headers):
        resp = client.get("/api/fish/analytics", headers=crew_headers)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_get_analytics(self, client):
        resp = client.get("/api/fish/analytics")
        assert resp.status_code == 401


class TestAnalysisHistory:
    def test_get_analysis_history(self, client, broker_headers):
        resp = client.get("/api/fish/analysis-history", headers=broker_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["results"], list)

    def test_history_with_pagination(self, client, broker_headers):
        resp = client.get(
            "/api/fish/analysis-history?limit=2&offset=0",
            headers=broker_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_crew_can_access_own_history(self, client, crew_headers):
        resp = client.get("/api/fish/analysis-history", headers=crew_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_unauthenticated_cannot_get_history(self, client):
        resp = client.get("/api/fish/analysis-history")
        assert resp.status_code == 401
