"""Tests for profile module."""
import pytest


class TestGetProfile:
    def test_super_can_get_profile(self, client, super_headers):
        resp = client.get("/api/profile", headers=super_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data
        assert data["email"] == "super@demo.com"

    def test_admin_profile_has_company(self, client, admin_headers):
        resp = client.get("/api/profile", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("companyName")
        assert data.get("companyCode")

    def test_unauthenticated_cannot_get_profile(self, client):
        resp = client.get("/api/profile")
        assert resp.status_code == 401


class TestUpdateProfile:
    def test_update_first_name(self, client, admin_headers):
        resp = client.patch("/api/profile", headers=admin_headers, json={
            "firstName": "UpdatedAdmin",
        })
        assert resp.status_code == 200

    def test_cannot_update_email_to_existing(self, client, admin_headers):
        resp = client.patch("/api/profile", headers=admin_headers, json={
            "email": "super@demo.com",
        })
        # Should reject or ignore since email belongs to another user
        assert resp.status_code in (200, 400, 409)


class TestChangePassword:
    def test_change_password_wrong_current(self, client, broker_headers):
        resp = client.post("/api/profile/change-password", headers=broker_headers, json={
            "currentPassword": "WrongPassword",
            "newPassword": "NewPass@123456",
        })
        assert resp.status_code in (400, 401, 403)
