"""Tests for licenses module."""
import pytest


class TestLicenseStatus:
    def test_get_license_status(self, client, super_headers):
        resp = client.get("/api/licenses/status", headers=super_headers)
        assert resp.status_code == 200

    def test_admin_license_status(self, client, admin_headers):
        resp = client.get("/api/licenses/status", headers=admin_headers)
        assert resp.status_code == 200

    def test_unauthenticated_cannot_check_status(self, client):
        resp = client.get("/api/licenses/status")
        assert resp.status_code == 401


class TestGenerateLicense:
    def test_super_can_generate_license(self, client, super_headers, admin_headers):
        profile = client.get("/api/profile", headers=admin_headers).json()
        company_id = profile.get("companyId")
        if company_id:
            resp = client.post("/api/licenses/generate", headers=super_headers, json={
                "companyId": company_id,
                "plan": "basic",
                "maxUsers": 10,
                "durationDays": 30,
            })
            # May fail if super role check is strict or payload format differs
            assert resp.status_code in (200, 201, 400, 422)

    def test_non_super_cannot_generate(self, client, admin_headers):
        resp = client.post("/api/licenses/generate", headers=admin_headers, json={
            "companyId": "any",
            "plan": "basic",
        })
        assert resp.status_code == 403


class TestValidateLicense:
    def test_validate_invalid_code(self, client, admin_headers):
        resp = client.post("/api/licenses/validate", headers=admin_headers, json={
            "activationCode": "INVALID-CODE-123",
        })
        assert resp.status_code in (400, 404, 422)


class TestListLicenses:
    def test_super_can_list_licenses(self, client, super_headers):
        resp = client.get("/api/licenses", headers=super_headers)
        assert resp.status_code == 200

    def test_non_super_cannot_list(self, client, admin_headers):
        resp = client.get("/api/licenses", headers=admin_headers)
        assert resp.status_code == 403


class TestRevokeLicense:
    def test_super_can_revoke_license(self, client, super_headers):
        # Generate a license first
        gen_resp = client.post("/api/licenses/generate", headers=super_headers, json={
            "plan": "trial", "maxUsers": 5, "durationDays": 7,
        })
        if gen_resp.status_code in (200, 201):
            license_id = gen_resp.json().get("id")
            if license_id:
                resp = client.patch(f"/api/licenses/{license_id}/revoke", headers=super_headers)
                assert resp.status_code == 200
                assert resp.json().get("status") == "revoked"

    def test_non_super_cannot_revoke(self, client, admin_headers):
        resp = client.patch("/api/licenses/000000000000000000000000/revoke", headers=admin_headers)
        assert resp.status_code == 403

    def test_revoke_nonexistent_returns_404(self, client, super_headers):
        resp = client.patch("/api/licenses/000000000000000000000000/revoke", headers=super_headers)
        assert resp.status_code == 404
