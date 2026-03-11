"""Tests for permissions module."""
import pytest


class TestListPermissions:
    def test_authenticated_can_list_permissions(self, client, admin_headers):
        resp = client.get("/api/permissions", headers=admin_headers)
        assert resp.status_code == 200
        perms = resp.json()
        assert isinstance(perms, list)
        assert len(perms) > 0
        perm_names = [p["name"] for p in perms]
        assert "user:read" in perm_names
        assert "boats:create" in perm_names

    def test_unauthenticated_cannot_list(self, client):
        resp = client.get("/api/permissions")
        assert resp.status_code == 401


class TestCreatePermission:
    def test_admin_can_create_permission(self, client, admin_headers):
        resp = client.post("/api/permissions", headers=admin_headers, json={
            "name": "test:custom",
            "description": "Test permission",
        })
        assert resp.status_code in (200, 201)

    def test_non_admin_cannot_create(self, client, broker_headers):
        resp = client.post("/api/permissions", headers=broker_headers, json={
            "name": "unauthorized:perm",
        })
        assert resp.status_code == 403
