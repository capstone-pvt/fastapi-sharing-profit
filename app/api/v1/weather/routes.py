from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import get_settings
from app.deps import get_current_user

router = APIRouter(prefix="/weather", tags=["weather"])

OPENWEATHER_BASE = "https://api.openweathermap.org/data/2.5"


def _sea_condition(wind_speed: float) -> str:
    if wind_speed > 10:
        return "Rough"
    if wind_speed > 7:
        return "Moderate to Rough"
    if wind_speed > 4:
        return "Moderate"
    return "Calm"


def _fishing_advisory(weather_main: str, wind_speed: float) -> dict:
    main_lower = weather_main.lower()
    if main_lower == "thunderstorm" or wind_speed > 10:
        return {
            "level": "danger",
            "message": "Not recommended — dangerous sea conditions",
        }
    if main_lower in ("rain", "drizzle") or wind_speed > 7:
        return {
            "level": "caution",
            "message": "Caution — rough seas expected",
        }
    if wind_speed > 5:
        return {
            "level": "moderate",
            "message": "Moderate — check local sea conditions",
        }
    return {
        "level": "favorable",
        "message": "Favorable — good conditions for fishing",
    }


@router.get("/current")
async def get_current_weather(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    user: dict[str, Any] = Depends(get_current_user),
):
    """Get current weather for a location with fishing insights."""
    settings = get_settings()
    if not settings.openweather_api_key:
        raise HTTPException(status_code=503, detail="Weather service not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{OPENWEATHER_BASE}/weather",
            params={
                "lat": lat,
                "lon": lon,
                "appid": settings.openweather_api_key,
                "units": "metric",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Weather API error")

    data = resp.json()

    # Enrich with fishing-specific insights
    wind_speed = data.get("wind", {}).get("speed", 0)
    weather_main = data.get("weather", [{}])[0].get("main", "")
    data["fishing"] = {
        "sea_condition": _sea_condition(wind_speed),
        "advisory": _fishing_advisory(weather_main, wind_speed),
    }

    return data


@router.get("/forecast")
async def get_weather_forecast(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    user: dict[str, Any] = Depends(get_current_user),
):
    """Get 5-day / 3-hour weather forecast for a location with fishing insights."""
    settings = get_settings()
    if not settings.openweather_api_key:
        raise HTTPException(status_code=503, detail="Weather service not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{OPENWEATHER_BASE}/forecast",
            params={
                "lat": lat,
                "lon": lon,
                "appid": settings.openweather_api_key,
                "units": "metric",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Weather API error")

    data = resp.json()

    # Reshape into daily summaries
    daily: dict[str, dict] = {}
    for item in data.get("list", []):
        date = item["dt_txt"].split(" ")[0]
        wind_speed = item["wind"]["speed"]
        weather_main = item["weather"][0]["main"]

        if date not in daily:
            daily[date] = {
                "date": date,
                "temp_min": item["main"]["temp_min"],
                "temp_max": item["main"]["temp_max"],
                "humidity": item["main"]["humidity"],
                "wind_speed": wind_speed,
                "wind_speed_max": wind_speed,
                "weather": weather_main,
                "description": item["weather"][0]["description"],
                "icon": item["weather"][0]["icon"],
                "sea_condition": _sea_condition(wind_speed),
                "fishing_advisory": _fishing_advisory(
                    weather_main, wind_speed
                ),
                "entries": [],
            }
        else:
            daily[date]["temp_min"] = min(
                daily[date]["temp_min"], item["main"]["temp_min"]
            )
            daily[date]["temp_max"] = max(
                daily[date]["temp_max"], item["main"]["temp_max"]
            )
            daily[date]["wind_speed_max"] = max(
                daily[date]["wind_speed_max"], wind_speed
            )
            # Update sea condition / advisory based on worst wind of the day
            max_wind = daily[date]["wind_speed_max"]
            daily[date]["sea_condition"] = _sea_condition(max_wind)
            daily[date]["fishing_advisory"] = _fishing_advisory(
                daily[date]["weather"], max_wind
            )

        daily[date]["entries"].append(
            {
                "dt_txt": item["dt_txt"],
                "temp": item["main"]["temp"],
                "weather": weather_main,
                "description": item["weather"][0]["description"],
                "icon": item["weather"][0]["icon"],
                "wind_speed": wind_speed,
                "humidity": item["main"]["humidity"],
            }
        )

    return {
        "city": data.get("city", {}),
        "daily": list(daily.values()),
    }
