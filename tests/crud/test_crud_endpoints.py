"""Tests for dynamic CRUD endpoints (boats, vessels, trips, etc.)."""
import pytest


CRUD_CASES = [
    ("boats", "/api/boats", {"name": "Test Boat"}),
    ("vessels", "/api/vessels", {"name": "Test Vessel"}),
    ("vessel-owners", "/api/vessel-owners", {"name": "Test Vessel Owner"}),
    ("trips", "/api/trips", {"name": "Test Trip"}),
    ("expenses", "/api/expenses", {"title": "Test Expense", "amount": 1200}),
    ("fish-sales", "/api/fish-sales", {"buyer": "Test Buyer", "amount": 2500}),
    ("catches", "/api/catches", {"notes": "Test Catch"}),
    ("crew", "/api/crew", {"name": "Test Crew"}),
    (
        "profit-sharing-policies",
        "/api/profit-sharing-policies",
        {"boatOwnerPercentage": 60, "fishermanPercentage": 40},
    ),
]


@pytest.mark.parametrize("label, path, payload", CRUD_CASES)
class TestCrudFlow:
    def test_create(self, client, super_headers, label, path, payload):
        resp = client.post(path, json=payload, headers=super_headers)
        assert resp.status_code in (200, 201), f"{label} create failed: {resp.text}"
        assert resp.json().get("id"), f"{label} create missing id"

    def test_list(self, client, super_headers, label, path, payload):
        resp = client.get(path, headers=super_headers)
        assert resp.status_code == 200, f"{label} list failed: {resp.text}"
        data = resp.json()
        assert "results" in data

    def test_create_read_update_delete(self, client, super_headers, label, path, payload):
        # Create
        create_resp = client.post(path, json=payload, headers=super_headers)
        assert create_resp.status_code in (200, 201), create_resp.text
        item_id = create_resp.json().get("id")
        assert item_id

        # Read
        get_resp = client.get(f"{path}/{item_id}", headers=super_headers)
        assert get_resp.status_code == 200
        assert get_resp.json().get("id") == item_id

        # Update
        update_resp = client.patch(
            f"{path}/{item_id}",
            json={"notes": f"Updated {label}"},
            headers=super_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json().get("notes") == f"Updated {label}"

        # Delete
        delete_resp = client.delete(f"{path}/{item_id}", headers=super_headers)
        assert delete_resp.status_code == 200
        assert delete_resp.json().get("status") == "deleted"

    def test_unauthenticated_cannot_access(self, client, label, path, payload):
        resp = client.get(path)
        assert resp.status_code in (401, 403)


EXTRA_CASES = [
    ("cash-advances", "/api/cash-advances", {"amount": 500, "purpose": "Test"}),
    ("forecasts", "/api/forecasts", {"notes": "Test Forecast"}),
    ("profit-shares", "/api/profit-shares", {"notes": "Test Share"}),
]


@pytest.mark.parametrize("label, path, payload", EXTRA_CASES)
class TestCrudReadAndCreate:
    def test_list(self, client, super_headers, label, path, payload):
        resp = client.get(path, headers=super_headers)
        assert resp.status_code == 200

    def test_create(self, client, super_headers, label, path, payload):
        resp = client.post(path, json=payload, headers=super_headers)
        assert resp.status_code in (200, 201)
