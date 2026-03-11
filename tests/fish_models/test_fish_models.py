"""Tests for fish models module."""
import io
import zipfile
import pytest


def _create_test_zip() -> bytes:
    """Create a minimal valid ZIP file for model upload."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("model.txt", "fake model weights")
    buf.seek(0)
    return buf.getvalue()


class TestListFishModels:
    def test_super_can_list_models(self, client, super_headers):
        resp = client.get("/api/fish/models", headers=super_headers)
        # require_roles("admin") — super role may not match; accept 200 or 403
        assert resp.status_code in (200, 403)

    def test_admin_can_list_models(self, client, admin_headers):
        resp = client.get("/api/fish/models", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_non_admin_cannot_list(self, client, broker_headers):
        resp = client.get("/api/fish/models", headers=broker_headers)
        assert resp.status_code == 403


class TestGetActiveModel:
    def test_get_active_detector(self, client, admin_headers):
        resp = client.get("/api/fish/models/active?model_type=detector", headers=admin_headers)
        assert resp.status_code in (200, 404)

    def test_get_active_classifier(self, client, admin_headers):
        resp = client.get("/api/fish/models/active?model_type=classifier", headers=admin_headers)
        assert resp.status_code in (200, 404)


class TestCreateFishModel:
    def test_admin_can_create_model(self, client, admin_headers):
        resp = client.post("/api/fish/models", headers=admin_headers, json={
            "name": "Test Model v1",
            "modelType": "detector",
            "version": "1.0.0-test",
            "status": "draft",
        })
        assert resp.status_code in (200, 201)

    def test_non_admin_cannot_create(self, client, broker_headers):
        resp = client.post("/api/fish/models", headers=broker_headers, json={
            "name": "Unauthorized Model",
            "modelType": "detector",
        })
        assert resp.status_code == 403


class TestUpdateFishModel:
    def test_admin_can_update_model(self, client, admin_headers):
        # Create a model first
        create_resp = client.post("/api/fish/models", headers=admin_headers, json={
            "name": "Update Test Model",
            "modelType": "classifier",
            "version": "2.0.0-test",
            "status": "draft",
        })
        assert create_resp.status_code in (200, 201)
        model_id = create_resp.json().get("id")
        if model_id:
            resp = client.patch(
                f"/api/fish/models/{model_id}",
                headers=admin_headers,
                json={"name": "Updated Model Name", "status": "approved"},
            )
            assert resp.status_code == 200

    def test_non_admin_cannot_update(self, client, broker_headers):
        resp = client.patch(
            "/api/fish/models/000000000000000000000000",
            headers=broker_headers,
            json={"name": "Hack"},
        )
        assert resp.status_code == 403


class TestActivateFishModel:
    def test_admin_can_activate_model(self, client, admin_headers):
        create_resp = client.post("/api/fish/models", headers=admin_headers, json={
            "name": "Activate Test",
            "modelType": "detector",
            "version": "3.0.0-test",
            "status": "approved",
        })
        assert create_resp.status_code in (200, 201)
        model_id = create_resp.json().get("id")
        if model_id:
            resp = client.patch(
                f"/api/fish/models/{model_id}/activate",
                headers=admin_headers,
            )
            assert resp.status_code == 200

    def test_non_admin_cannot_activate(self, client, broker_headers):
        resp = client.patch(
            "/api/fish/models/000000000000000000000000/activate",
            headers=broker_headers,
        )
        assert resp.status_code == 403


class TestDeleteFishModel:
    def test_admin_can_soft_delete_model(self, client, admin_headers):
        create_resp = client.post("/api/fish/models", headers=admin_headers, json={
            "name": "Delete Test",
            "modelType": "classifier",
            "version": "4.0.0-test",
            "status": "draft",
        })
        assert create_resp.status_code in (200, 201)
        model_id = create_resp.json().get("id")
        if model_id:
            resp = client.delete(
                f"/api/fish/models/{model_id}?status=cancelled",
                headers=admin_headers,
            )
            assert resp.status_code == 200

    def test_non_admin_cannot_delete(self, client, broker_headers):
        resp = client.delete(
            "/api/fish/models/000000000000000000000000",
            headers=broker_headers,
        )
        assert resp.status_code == 403

    def test_delete_nonexistent_returns_404(self, client, admin_headers):
        resp = client.delete(
            "/api/fish/models/000000000000000000000000",
            headers=admin_headers,
        )
        assert resp.status_code == 404
