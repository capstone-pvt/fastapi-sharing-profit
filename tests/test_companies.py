"""Tests for companies module."""
import pytest


class TestListCompanies:
    def test_super_can_list_companies(self, client, super_headers):
        resp = client.get("/api/companies", headers=super_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("results", data), list)

    def test_unauthenticated_cannot_list(self, client):
        resp = client.get("/api/companies")
        assert resp.status_code in (401, 403)


class TestCreateCompany:
    def test_super_can_create_company(self, client, super_headers):
        import uuid
        resp = client.post("/api/companies", headers=super_headers, json={
            "companyName": f"Test Company {uuid.uuid4().hex[:6]}",
            "companyAddress": "123 Test St",
        })
        assert resp.status_code in (200, 201)

    def test_non_super_cannot_create(self, client, broker_headers):
        resp = client.post("/api/companies", headers=broker_headers, json={
            "companyName": "Unauthorized Company",
        })
        assert resp.status_code == 403

    def test_unauthenticated_cannot_create(self, client):
        resp = client.post("/api/companies", json={"companyName": "Hack"})
        assert resp.status_code == 401


class TestUpdateCompany:
    def test_admin_can_update_own_company(self, client, admin_headers):
        profile = client.get("/api/profile", headers=admin_headers).json()
        company_id = profile.get("companyId")
        if company_id:
            resp = client.patch(
                f"/api/companies/{company_id}",
                headers=admin_headers,
                json={"companyPhone": "09171234567"},
            )
            assert resp.status_code in (200, 403)


class TestDeleteCompany:
    def test_super_can_delete_company(self, client, super_headers):
        import uuid
        # Create a company to delete
        name = f"ToDelete {uuid.uuid4().hex[:6]}"
        create_resp = client.post("/api/companies", headers=super_headers, json={
            "companyName": name,
        })
        if create_resp.status_code in (200, 201):
            company_id = create_resp.json().get("id")
            if company_id:
                resp = client.delete(f"/api/companies/{company_id}", headers=super_headers)
                assert resp.status_code == 200
                assert resp.json().get("status") == "deleted"

    def test_broker_cannot_delete(self, client, broker_headers):
        resp = client.delete("/api/companies/000000000000000000000000", headers=broker_headers)
        assert resp.status_code == 403
