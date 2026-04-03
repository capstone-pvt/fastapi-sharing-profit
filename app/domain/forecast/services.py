"""Seasonal species forecast service.

Predicts which fish species are in-season based on the current month,
integrates weather conditions for fishing advisories, and returns
species availability with estimated price ranges.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def get_seasonal_species(
    species_list: list[dict[str, Any]],
    month: int | None = None,
) -> list[dict[str, Any]]:
    """Return species that are in-season for the given month.

    Each species is tagged with availability level:
    - "peak": current month is in peakMonths
    - "available": species is year-round (peakMonths covers all 12 months)
    - "off_season": current month is NOT in peakMonths
    """
    if month is None:
        month = datetime.now(timezone.utc).month

    results: list[dict[str, Any]] = []

    for sp in species_list:
        peak_months = sp.get("peakMonths") or list(range(1, 13))
        weight_range = sp.get("weightRange") or [0, 0]
        price_range = sp.get("pricePerKg") or [0, 0]

        is_peak = month in peak_months
        is_year_round = len(peak_months) >= 12

        if is_peak:
            availability = "peak" if not is_year_round else "available"
            price_factor = 1.0  # normal price during peak
        else:
            availability = "off_season"
            price_factor = 1.3  # ~30% higher price off-season (scarce)

        results.append({
            "name": sp.get("name"),
            "scientificName": sp.get("scientificName"),
            "englishName": sp.get("englishName"),
            "localName": sp.get("localName"),
            "habitat": sp.get("habitat", "unknown"),
            "availability": availability,
            "peakMonths": peak_months,
            "currentMonth": month,
            "weightRange": {
                "minKg": weight_range[0],
                "maxKg": weight_range[1],
            },
            "estimatedPricePerKg": {
                "minPhp": round(price_range[0] * price_factor),
                "maxPhp": round(price_range[1] * price_factor),
                "note": "Prices may be higher off-season" if not is_peak else "In-season pricing",
            },
        })

    # Sort: peak first, then available, then off_season
    order = {"peak": 0, "available": 1, "off_season": 2}
    results.sort(key=lambda x: (order.get(x["availability"], 3), x["name"]))
    return results


def build_seasonal_forecast(
    species_list: list[dict[str, Any]],
    month: int | None = None,
    weather_data: dict[str, Any] | None = None,
    habitat_filter: str | None = None,
) -> dict[str, Any]:
    """Build a complete seasonal forecast with weather integration.

    Returns a forecast document with species availability, weather advisory,
    and summary statistics.
    """
    if month is None:
        month = datetime.now(timezone.utc).month

    seasonal = get_seasonal_species(species_list, month)

    # Filter by habitat if requested
    if habitat_filter:
        seasonal = [
            s for s in seasonal
            if s["habitat"].lower() == habitat_filter.lower()
        ]

    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    peak_species = [s for s in seasonal if s["availability"] == "peak"]
    available_species = [s for s in seasonal if s["availability"] == "available"]
    off_season_species = [s for s in seasonal if s["availability"] == "off_season"]

    forecast: dict[str, Any] = {
        "month": month,
        "monthName": month_names[month] if 1 <= month <= 12 else "Unknown",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "totalSpecies": len(seasonal),
            "peakSpecies": len(peak_species),
            "availableSpecies": len(available_species),
            "offSeasonSpecies": len(off_season_species),
        },
        "species": seasonal,
    }

    # Integrate weather if provided
    if weather_data:
        wind_speed = weather_data.get("wind", {}).get("speed", 0)
        weather_main = weather_data.get("weather", [{}])[0].get("main", "")
        temp = weather_data.get("main", {}).get("temp")

        forecast["weather"] = {
            "temperature": temp,
            "windSpeed": wind_speed,
            "condition": weather_main,
            "seaCondition": _sea_condition(wind_speed),
            "fishingAdvisory": _fishing_advisory(weather_main, wind_speed),
        }

        # Adjust recommendations based on weather
        if wind_speed > 10 or weather_main.lower() == "thunderstorm":
            forecast["recommendation"] = (
                "Dangerous weather conditions. Fishing not recommended today. "
                "Consider freshwater species in sheltered areas."
            )
            # Highlight freshwater species as alternatives
            for sp in forecast["species"]:
                if sp["habitat"] == "freshwater" and sp["availability"] != "off_season":
                    sp["weatherNote"] = "Safe option - freshwater/sheltered"
                elif sp["habitat"] == "marine":
                    sp["weatherNote"] = "Not recommended - rough seas"
        elif wind_speed > 7:
            forecast["recommendation"] = (
                "Rough seas expected. Exercise caution for marine fishing. "
                "Brackish and freshwater fishing is safe."
            )
        else:
            forecast["recommendation"] = (
                "Good fishing conditions. Both marine and freshwater fishing are favorable."
            )

    return forecast


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
        return {"level": "danger", "message": "Not recommended - dangerous sea conditions"}
    if main_lower in ("rain", "drizzle") or wind_speed > 7:
        return {"level": "caution", "message": "Caution - rough seas expected"}
    if wind_speed > 5:
        return {"level": "moderate", "message": "Moderate - check local sea conditions"}
    return {"level": "favorable", "message": "Favorable - good conditions for fishing"}
