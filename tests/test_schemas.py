from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_server.schemas import (
    SearchDocsInput,
    SqlQueryInput,
    WeatherCoords,
    WeatherForecastInput,
)


def test_sql_input_enforces_lengths() -> None:
    with pytest.raises(ValidationError):
        SqlQueryInput(query="")
    with pytest.raises(ValidationError):
        SqlQueryInput(query="SELECT 1", limit=10_000)


def test_weather_coords_validates_range() -> None:
    WeatherCoords(latitude=0, longitude=0)
    with pytest.raises(ValidationError):
        WeatherCoords(latitude=91, longitude=0)
    with pytest.raises(ValidationError):
        WeatherCoords(latitude=0, longitude=181)


def test_forecast_days_bounded() -> None:
    WeatherForecastInput(latitude=0, longitude=0, days=14)
    with pytest.raises(ValidationError):
        WeatherForecastInput(latitude=0, longitude=0, days=30)


def test_search_top_k_bounded() -> None:
    SearchDocsInput(query="x", top_k=1)
    with pytest.raises(ValidationError):
        SearchDocsInput(query="x", top_k=999)
