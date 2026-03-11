"""Tests for roles module."""
import pytest


class TestListRoles:
    def test_authenticated_user_can_list_roles(self, client, admin_headers):
        resp = client.get("/api/roles", headers=admin_headers)
        assert resp.status_code == 200
        roles = resp.json()
        assert isinstance(roles, list)
        role_names = [r["name"] for r in roles]
        assert "super" in role_names
        assert "admin" in role_names
        assert "broker" in role_names
        assert "owner" in role_names
        assert "crew" in role_names

    def test_unauthenticated_cannot_list_roles(self, client):
        resp = client.get("/api/roles")
        assert resp.status_code == 401


class TestGetRole:
    def test_get_role_by_id(self, client, admin_headers):
        list_resp = client.get("/api/roles", headers=admin_headers)
        roles = list_resp.json()
        if roles and isinstance(roles, list) and len(roles) > 0:
            role_id = roles[0]["id"]
            resp = client.get(f"/api/roles/{role_id}", headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["id"] == role_id


class TestCreateRole:
    def test_admin_can_create_role(self, client, admin_headers):
        resp = client.post("/api/roles", headers=admin_headers, json={
            "name": "test_custom_role",
            "description": "A test role",
        })
        assert resp.status_code in (200, 201)
        assert resp.json().get("name") == "test_custom_role"

    def test_non_admin_cannot_create_role(self, client, broker_headers):
        resp = client.post("/api/roles", headers=broker_headers, json={
            "name": "unauthorized_role",
        })
        assert resp.status_code == 403


class TestDeleteRole:
    def test_cannot_delete_admin_role(self, client, admin_headers):
        list_resp = client.get("/api/roles", headers=admin_headers)
        roles = list_resp.json()
        admin_role = next((r for r in roles if r["name"] == "admin"), None)
        if admin_role:
            resp = client.delete(f"/api/roles/{admin_role['id']}", headers=admin_headers)
            assert resp.status_code in (400, 403)
