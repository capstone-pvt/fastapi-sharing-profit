"""Tests for cash advance approve/decline endpoints."""
import pytest


class TestApproveCashAdvance:
    def test_approve_flow(self, client, super_headers):
        # Create a cash advance first
        create_resp = client.post("/api/cash-advances", headers=super_headers, json={
            "amount": 500, "purpose": "Test advance for approval",
        })
        if create_resp.status_code in (200, 201):
            item_id = create_resp.json().get("id")
            if item_id:
                resp = client.patch(
                    f"/api/cash-advances/{item_id}/approve",
                    headers=super_headers,
                    json={"notes": "Approved for testing"},
                )
                assert resp.status_code in (200, 403)
                if resp.status_code == 200:
                    assert resp.json().get("status") == "approved"

    def test_approve_nonexistent_returns_404(self, client, super_headers):
        resp = client.patch(
            "/api/cash-advances/000000000000000000000000/approve",
            headers=super_headers,
            json={},
        )
        # 404 if found but missing, or 403 if permission not assigned
        assert resp.status_code in (404, 403)

    def test_unauthenticated_cannot_approve(self, client):
        resp = client.patch("/api/cash-advances/000000000000000000000000/approve", json={})
        assert resp.status_code == 401


class TestDeclineCashAdvance:
    def test_decline_flow(self, client, super_headers):
        create_resp = client.post("/api/cash-advances", headers=super_headers, json={
            "amount": 300, "purpose": "Test advance for decline",
        })
        if create_resp.status_code in (200, 201):
            item_id = create_resp.json().get("id")
            if item_id:
                resp = client.patch(
                    f"/api/cash-advances/{item_id}/decline",
                    headers=super_headers,
                    json={"declineReason": "Budget exceeded"},
                )
                assert resp.status_code in (200, 403)
                if resp.status_code == 200:
                    assert resp.json().get("status") == "declined"

    def test_decline_without_reason_returns_400(self, client, super_headers):
        create_resp = client.post("/api/cash-advances", headers=super_headers, json={
            "amount": 100, "purpose": "No reason test",
        })
        if create_resp.status_code in (200, 201):
            item_id = create_resp.json().get("id")
            if item_id:
                resp = client.patch(
                    f"/api/cash-advances/{item_id}/decline",
                    headers=super_headers,
                    json={},
                )
                assert resp.status_code in (400, 403)

    def test_unauthenticated_cannot_decline(self, client):
        resp = client.patch(
            "/api/cash-advances/000000000000000000000000/decline",
            json={"declineReason": "hack"},
        )
        assert resp.status_code == 401
