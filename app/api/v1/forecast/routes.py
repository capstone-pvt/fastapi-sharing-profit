from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import get_settings
from app.deps import get_current_user, require_permissions
from app.domain.forecast.services import build_seasonal_forecast
from app.infrastructure.fish_species.repository import list_active_species

router = APIRouter(prefix="/forecasts", tags=["forecasts"])

OPENWEATHER_BASE = "https://api.openweathermap.org/data/2.5"


@router.get("/seasonal")
async def get_seasonal_forecast(
    month: int | None = Query(None, ge=1, le=12, description="Month (1-12). Defaults to current month."),
    habitat: str | None = Query(None, description="Filter by habitat: marine, freshwater, brackish"),
    lat: float | None = Query(None, description="Latitude for weather integration"),
    lon: float | None = Query(None, description="Longitude for weather integration"),
    user: dict[str, Any] = Depends(require_permissions("forecasts:read")),
):
    """Get seasonal species forecast with weather-integrated fishing advisory.

    Returns which species are in-season, estimated prices, and
    weather-based fishing recommendations when lat/lon provided.
    """
    species_list = await list_active_species()

    # Fetch weather if coordinates provided
    weather_data = None
    if lat is not None and lon is not None:
        settings = get_settings()
        if settings.openweather_api_key:
            try:
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
                if resp.status_code == 200:
                    weather_data = resp.json()
            except Exception:
                pass  # Weather is optional enrichment

    forecast = build_seasonal_forecast(
        species_list=species_list,
        month=month,
        weather_data=weather_data,
        habitat_filter=habitat,
    )

    return forecast


@router.get("/species-calendar")
async def get_species_calendar(
    user: dict[str, Any] = Depends(require_permissions("forecasts:read")),
):
    """Get a 12-month calendar showing peak months for all species.

    Useful for planning fishing trips and forecasting catch availability.
    """
    species_list = await list_active_species()

    calendar: dict[str, list[dict[str, Any]]] = {}
    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    for m in range(1, 13):
        month_species = []
        for sp in species_list:
            peak_months = sp.get("peakMonths") or list(range(1, 13))
            if m in peak_months:
                price_range = sp.get("pricePerKg") or [0, 0]
                month_species.append({
                    "name": sp.get("name"),
                    "localName": sp.get("localName"),
                    "habitat": sp.get("habitat", "unknown"),
                    "pricePerKg": {"minPhp": price_range[0], "maxPhp": price_range[1]},
                })
        calendar[month_names[m]] = month_species

    return {
        "calendar": calendar,
        "totalSpecies": len(species_list),
    }


@router.get("/price-guide")
async def get_price_guide(
    month: int | None = Query(None, ge=1, le=12, description="Month (1-12). Defaults to current month."),
    user: dict[str, Any] = Depends(require_permissions("forecasts:read")),
):
    """Get estimated market prices for all species for the given month.

    Prices adjust based on seasonality (off-season species cost more).
    """
    from datetime import datetime, timezone

    if month is None:
        month = datetime.now(timezone.utc).month

    species_list = await list_active_species()
    prices: list[dict[str, Any]] = []

    for sp in species_list:
        peak_months = sp.get("peakMonths") or list(range(1, 13))
        price_range = sp.get("pricePerKg") or [0, 0]
        weight_range = sp.get("weightRange") or [0, 0]
        is_peak = month in peak_months
        factor = 1.0 if is_peak else 1.3

        avg_price = round((price_range[0] + price_range[1]) / 2 * factor)
        avg_weight = round((weight_range[0] + weight_range[1]) / 2, 2)

        prices.append({
            "name": sp.get("name"),
            "localName": sp.get("localName"),
            "habitat": sp.get("habitat"),
            "inSeason": is_peak,
            "estimatedPricePerKg": avg_price,
            "priceRange": {
                "minPhp": round(price_range[0] * factor),
                "maxPhp": round(price_range[1] * factor),
            },
            "averageWeightKg": avg_weight,
            "estimatedPricePerFish": round(avg_price * avg_weight),
        })

    prices.sort(key=lambda x: x["estimatedPricePerKg"])

    return {
        "month": month,
        "prices": prices,
    }
