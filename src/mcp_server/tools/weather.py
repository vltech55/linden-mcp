from __future__ import annotations

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from mcp_server.core.logging import get_logger
from mcp_server.schemas import (
    WeatherCoords,
    WeatherCurrent,
    WeatherDay,
    WeatherForecast,
    WeatherForecastInput,
)

log = get_logger(__name__)

# Open-Meteo is free and key-less; ideal for a portfolio demo.
_BASE = "https://api.open-meteo.com/v1/forecast"


async def _get(params: dict) -> dict:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.HTTPError,)),
        reraise=True,
    ):
        with attempt:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_BASE, params=params)
                resp.raise_for_status()
                return resp.json()  # type: ignore[no-any-return]
    raise RuntimeError("weather retries exhausted")


async def weather_current(coords: WeatherCoords) -> WeatherCurrent:
    data = await _get(
        {
            "latitude": coords.latitude,
            "longitude": coords.longitude,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        }
    )
    cur = data.get("current", {})
    return WeatherCurrent(
        latitude=coords.latitude,
        longitude=coords.longitude,
        temperature_c=float(cur.get("temperature_2m", 0.0)),
        relative_humidity_pct=cur.get("relative_humidity_2m"),
        wind_speed_kmh=cur.get("wind_speed_10m"),
        weather_code=cur.get("weather_code"),
        observed_at=str(cur.get("time", "")),
    )


async def weather_forecast(params: WeatherForecastInput) -> WeatherForecast:
    data = await _get(
        {
            "latitude": params.latitude,
            "longitude": params.longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
            "forecast_days": params.days,
        }
    )
    daily = data.get("daily", {})
    days: list[WeatherDay] = []
    for i, date in enumerate(daily.get("time", [])):
        days.append(
            WeatherDay(
                date=str(date),
                temperature_max_c=_get_idx(daily.get("temperature_2m_max"), i),
                temperature_min_c=_get_idx(daily.get("temperature_2m_min"), i),
                precipitation_mm=_get_idx(daily.get("precipitation_sum"), i),
                weather_code=_get_idx(daily.get("weather_code"), i),
            )
        )
    return WeatherForecast(
        latitude=params.latitude,
        longitude=params.longitude,
        days=days,
    )


def _get_idx(seq: list | None, i: int) -> float | int | None:
    if not seq or i >= len(seq):
        return None
    return seq[i]
