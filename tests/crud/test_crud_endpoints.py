import pytest


def _login_as_super(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "super@example.com", "password": "Admin@123456"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    access_token = data.get("accessToken")
    assert access_token, "Missing access token in login response"
    return {"Authorization": f"Bearer {access_token}"}


CRUD_CASES = [
    ("boats", "/api/boats", {"name": "Test Boat"}),
    ("vessels", "/api/vessels", {"name": "Test Vessel"}),
    ("vessel-owners", "/api/vessel-owners", {"name": "Test Vessel Owner"}),
    ("trips", "/api/trips", {"name": "Test Trip"}),
    ("expenses", "/api/expenses", {"title": "Test Expense", "amount": 1200}),
    ("fish-sales", "/api/fish-sales", {"buyer": "Test Buyer", "amount": 2500}),
    ("cash-advances", "/api/cash-advances", {"amount": 500, "purpose": "Test"}),
    ("forecasts", "/api/forecasts", {"notes": "Test Forecast"}),
    ("catches", "/api/catches", {"notes": "Test Catch"}),
    ("crew", "/api/crew", {"name": "Test Crew"}),
    (
        "profit-sharing-policies",
        "/api/profit-sharing-policies",
        {"boatOwnerPercentage": 60, "fishermanPercentage": 40},
    ),
]


@pytest.mark.parametrize("label, path, payload", CRUD_CASES)
def test_crud_flow(client, label, path, payload):
    headers = _login_as_super(client)

    create_response = client.post(path, json=payload, headers=headers)
    assert create_response.status_code in (200, 201), create_response.text
    created = create_response.json()
    item_id = created.get("id")
    assert item_id, f"{label} create missing id"

    list_response = client.get(path, headers=headers)
    assert list_response.status_code == 200, list_response.text
    results = list_response.json().get("results", [])
    assert any(item.get("id") == item_id for item in results)

    get_response = client.get(f"{path}/{item_id}", headers=headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json().get("id") == item_id

    update_payload = {"notes": f"Updated {label}"}
    update_response = client.patch(
        f"{path}/{item_id}",
        json=update_payload,
        headers=headers,
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json().get("notes") == update_payload["notes"]

    delete_response = client.delete(f"{path}/{item_id}", headers=headers)
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json().get("status") == "deleted"
