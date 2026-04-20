"""Tests for the trips router filter behavior (B1)."""


class TestCrewIdFilter:
    def test_crew_id_filter_is_accepted(self, client, super_headers):
        # Known crewId — the filter simply has to be accepted server-side
        # and translate into an array-membership query. If the filter is not
        # recognised, the backend would ignore it and return all trips; we
        # assert the endpoint handles the param without error.
        resp = client.get(
            "/api/trips",
            headers=super_headers,
            params={"crewId": "000000000000000000000001"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body
        assert "total" in body
        # When no trips match, total must be 0 (not the whole collection)
        for trip in body["results"]:
            assert "000000000000000000000001" in (trip.get("crewIds") or [])

    def test_unknown_filter_keys_are_ignored(self, client, super_headers):
        resp = client.get(
            "/api/trips",
            headers=super_headers,
            params={"bogusField": "xyz"},
        )
        assert resp.status_code == 200
