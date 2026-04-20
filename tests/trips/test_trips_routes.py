"""Tests for the trips router filter behavior (B1)."""


class TestCrewIdFilter:
    def test_crew_id_filter_is_accepted(self, client, super_headers):
        target_crew_id = "000000000000000000000001"
        create_resp = client.post(
            "/api/trips",
            headers=super_headers,
            json={"crewIds": [target_crew_id], "name": "filter-test-trip"},
        )
        assert create_resp.status_code in (200, 201)

        resp = client.get(
            "/api/trips",
            headers=super_headers,
            params={"crewId": target_crew_id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        for trip in body["results"]:
            assert target_crew_id in (trip.get("crewIds") or [])

    def test_unknown_filter_keys_are_ignored(self, client, super_headers):
        resp = client.get(
            "/api/trips",
            headers=super_headers,
            params={"bogusField": "xyz"},
        )
        assert resp.status_code == 200
