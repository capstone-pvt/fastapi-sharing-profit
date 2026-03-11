"""Tests for role-based access control across modules."""
import pytest


class TestBrokerPermissions:
    """Broker should have access to boats, vessels, trips, fish-sales, expenses, etc."""

    def test_broker_can_list_boats(self, client, broker_headers):
        resp = client.get("/api/boats", headers=broker_headers)
        assert resp.status_code == 200

    def test_broker_can_create_boat(self, client, broker_headers):
        resp = client.post("/api/boats", headers=broker_headers, json={
            "name": "Broker Boat",
        })
        assert resp.status_code in (200, 201)

    def test_broker_can_list_trips(self, client, broker_headers):
        resp = client.get("/api/trips", headers=broker_headers)
        assert resp.status_code == 200

    def test_broker_can_list_users(self, client, broker_headers):
        resp = client.get("/api/users", headers=broker_headers)
        assert resp.status_code == 200

    def test_broker_can_list_fish_sales(self, client, broker_headers):
        resp = client.get("/api/fish-sales", headers=broker_headers)
        assert resp.status_code == 200

    def test_broker_can_list_expenses(self, client, broker_headers):
        resp = client.get("/api/expenses", headers=broker_headers)
        assert resp.status_code == 200

    def test_broker_cannot_manage_roles(self, client, broker_headers):
        resp = client.post("/api/roles", headers=broker_headers, json={"name": "hack"})
        assert resp.status_code == 403

    def test_broker_cannot_manage_permissions(self, client, broker_headers):
        resp = client.post("/api/permissions", headers=broker_headers, json={"name": "hack"})
        assert resp.status_code == 403


class TestCrewPermissions:
    """Crew should only have read access to limited resources."""

    def test_crew_can_read_profit_shares(self, client, crew_headers):
        resp = client.get("/api/profit-shares", headers=crew_headers)
        assert resp.status_code == 200

    def test_crew_can_read_catches(self, client, crew_headers):
        resp = client.get("/api/catches", headers=crew_headers)
        assert resp.status_code == 200

    def test_crew_can_read_fish_sales(self, client, crew_headers):
        resp = client.get("/api/fish-sales", headers=crew_headers)
        assert resp.status_code == 200

    def test_crew_cannot_list_users(self, client, crew_headers):
        resp = client.get("/api/users", headers=crew_headers)
        assert resp.status_code == 403

    def test_crew_cannot_create_boats(self, client, crew_headers):
        resp = client.post("/api/boats", headers=crew_headers, json={"name": "Hack"})
        assert resp.status_code == 403

    def test_crew_cannot_manage_roles(self, client, crew_headers):
        resp = client.post("/api/roles", headers=crew_headers, json={"name": "hack"})
        assert resp.status_code == 403


class TestSuperUserRestrictions:
    """Super user cannot edit/delete themselves."""

    def test_super_cannot_edit_self(self, client, super_headers):
        profile = client.get("/api/profile", headers=super_headers).json()
        user_id = profile.get("userId") or profile.get("id")
        if user_id:
            resp = client.patch(
                f"/api/users/{user_id}",
                headers=super_headers,
                json={"firstName": "Hacked"},
            )
            assert resp.status_code == 403

    def test_super_cannot_delete_self(self, client, super_headers):
        profile = client.get("/api/profile", headers=super_headers).json()
        user_id = profile.get("userId") or profile.get("id")
        if user_id:
            resp = client.delete(f"/api/users/{user_id}", headers=super_headers)
            assert resp.status_code == 403
