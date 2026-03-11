"""Tests for fish species module."""
import pytest


class TestListFishSpecies:
    def test_admin_can_list_all_species(self, client, admin_headers):
        resp = client.get("/api/fish/species", headers=admin_headers)
        assert resp.status_code == 200

    def test_active_species_for_authenticated(self, client, broker_headers):
        resp = client.get("/api/fish/species/active", headers=broker_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_unauthenticated_cannot_list(self, client):
        resp = client.get("/api/fish/species")
        assert resp.status_code in (401, 403)


class TestCreateFishSpecies:
    def test_admin_can_create_species(self, client, admin_headers):
        resp = client.post("/api/fish/species", headers=admin_headers, json={
            "name": "Test Tuna",
            "scientificName": "Thunnus test",
            "englishName": "Test Tuna",
            "localName": "Test Tulingan",
            "isActive": True,
        })
        assert resp.status_code in (200, 201)

    def test_non_admin_cannot_create(self, client, broker_headers):
        resp = client.post("/api/fish/species", headers=broker_headers, json={
            "name": "Unauthorized Fish",
        })
        assert resp.status_code == 403
