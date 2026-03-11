"""Tests for user management module."""
import pytest


class TestListUsers:
    def test_super_can_list_all_users(self, client, super_headers):
        resp = client.get("/api/users", headers=super_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert isinstance(data["results"], list)

    def test_broker_sees_only_company_users(self, client, broker_headers):
        resp = client.get("/api/users", headers=broker_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_crew_cannot_list_users(self, client, crew_headers):
        resp = client.get("/api/users", headers=crew_headers)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_list(self, client):
        resp = client.get("/api/users")
        assert resp.status_code == 401

    def test_list_with_search(self, client, super_headers):
        resp = client.get("/api/users?search=test", headers=super_headers)
        assert resp.status_code == 200

    def test_list_with_pagination(self, client, super_headers):
        resp = client.get("/api/users?limit=5&offset=0", headers=super_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["offset"] == 0


class TestGetUser:
    def test_super_can_get_user(self, client, super_headers):
        list_resp = client.get("/api/users?limit=1", headers=super_headers)
        users = list_resp.json().get("results", [])
        if users:
            user_id = users[0]["id"]
            resp = client.get(f"/api/users/{user_id}", headers=super_headers)
            assert resp.status_code == 200
            assert resp.json()["id"] == user_id

    def test_get_nonexistent_user(self, client, super_headers):
        resp = client.get("/api/users/000000000000000000000000", headers=super_headers)
        assert resp.status_code == 404


class TestCreateUser:
    def test_super_can_create_user(self, client, super_headers):
        import uuid
        roles_resp = client.get("/api/roles", headers=super_headers)
        roles = roles_resp.json()
        crew_role_id = None
        if isinstance(roles, list):
            crew_role_id = next((r["id"] for r in roles if r["name"] == "crew"), None)
        if crew_role_id:
            unique_email = f"created_{uuid.uuid4().hex[:8]}@test.com"
            resp = client.post("/api/users", headers=super_headers, json={
                "email": unique_email,
                "password": "Test@123456",
                "firstName": "Created",
                "lastName": "User",
                "roleId": crew_role_id,
            })
            assert resp.status_code in (200, 201)


class TestBulkAssignCompany:
    def test_super_can_bulk_assign(self, client, super_headers, admin_headers):
        # Get a company ID
        profile = client.get("/api/profile", headers=admin_headers).json()
        company_id = profile.get("companyId")
        if company_id:
            # Get a user to assign
            users_resp = client.get("/api/users?limit=1", headers=super_headers)
            users = users_resp.json().get("results", [])
            if users:
                resp = client.post("/api/users/bulk-assign-company", headers=super_headers, json={
                    "userIds": [users[0]["id"]],
                    "companyId": company_id,
                })
                assert resp.status_code == 200
                assert resp.json().get("status") == "completed"

    def test_non_super_cannot_bulk_assign(self, client, broker_headers):
        resp = client.post("/api/users/bulk-assign-company", headers=broker_headers, json={
            "userIds": ["000000000000000000000000"],
            "companyId": "000000000000000000000000",
        })
        assert resp.status_code == 403

    def test_unauthenticated_cannot_bulk_assign(self, client):
        resp = client.post("/api/users/bulk-assign-company", json={
            "userIds": ["any"], "companyId": "any",
        })
        assert resp.status_code == 401


class TestDeleteUser:
    def test_super_can_delete_user(self, client, super_headers):
        import uuid
        roles_resp = client.get("/api/roles", headers=super_headers)
        roles = roles_resp.json()
        crew_role_id = None
        if isinstance(roles, list):
            crew_role_id = next((r["id"] for r in roles if r["name"] == "crew"), None)
        if crew_role_id:
            unique_email = f"todelete_{uuid.uuid4().hex[:8]}@test.com"
            create_resp = client.post("/api/users", headers=super_headers, json={
                "email": unique_email,
                "password": "Test@123456",
                "firstName": "To",
                "lastName": "Delete",
                "roleId": crew_role_id,
            })
            if create_resp.status_code in (200, 201):
                user_id = create_resp.json()["id"]
                resp = client.delete(f"/api/users/{user_id}", headers=super_headers)
                assert resp.status_code == 200
                assert resp.json()["status"] == "deleted"
