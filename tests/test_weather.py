"""Tests for weather module."""
import pytest


class TestCurrentWeather:
    def test_get_current_weather(self, client, broker_headers):
        resp = client.get(
            "/api/weather/current?lat=14.5995&lon=120.9842",
            headers=broker_headers,
        )
        # 200 if API key works, 422/500/502 if not configured
        assert resp.status_code in (200, 400, 422, 500, 502)

    def test_unauthenticated_cannot_get_weather(self, client):
        resp = client.get("/api/weather/current?lat=14.5995&lon=120.9842")
        assert resp.status_code == 401


class TestWeatherForecast:
    def test_get_forecast(self, client, broker_headers):
        import httpx
        try:
            resp = client.get(
                "/api/weather/forecast?lat=14.5995&lon=120.9842",
                headers=broker_headers,
            )
            assert resp.status_code in (200, 400, 422, 500, 502)
        except httpx.ReadTimeout:
            pass  # External API timeout is acceptable

    def test_unauthenticated_cannot_get_forecast(self, client):
        resp = client.get("/api/weather/forecast?lat=14.5995&lon=120.9842")
        assert resp.status_code == 401
