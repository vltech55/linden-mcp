from __future__ import annotations

from pydantic import BaseModel, Field


class SqlQueryInput(BaseModel):
    query: str = Field(min_length=1, max_length=4000, description="Read-only SQL (SELECT/CTE).")
    limit: int = Field(default=100, ge=1, le=500, description="Max rows returned.")


class SqlQueryRow(BaseModel):
    model_config = {"extra": "allow"}


class SqlQueryResult(BaseModel):
    rows: list[dict]
    row_count: int
    truncated: bool
    elapsed_ms: float


class WeatherCoords(BaseModel):
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class WeatherCurrent(BaseModel):
    latitude: float
    longitude: float
    temperature_c: float
    relative_humidity_pct: float | None = None
    wind_speed_kmh: float | None = None
    weather_code: int | None = None
    observed_at: str


class WeatherForecastInput(WeatherCoords):
    days: int = Field(default=3, ge=1, le=14)


class WeatherDay(BaseModel):
    date: str
    temperature_max_c: float | None
    temperature_min_c: float | None
    precipitation_mm: float | None
    weather_code: int | None


class WeatherForecast(BaseModel):
    latitude: float
    longitude: float
    days: list[WeatherDay]


class SearchDocsInput(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class DocumentHit(BaseModel):
    id: str
    title: str
    url: str | None
    snippet: str
    similarity: float


class SearchDocsResult(BaseModel):
    query: str
    hits: list[DocumentHit]


class ListTablesResult(BaseModel):
    tables: list[str]
