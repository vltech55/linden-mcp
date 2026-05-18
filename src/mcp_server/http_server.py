"""HTTP transport for the MCP server.

The stdio server (server.py) is what Claude Desktop hooks up to. This module
adds a thin FastAPI surface with API-key auth and per-key rate limiting for
remote clients, exposing the same tools as JSON endpoints. It is NOT a
replacement for stdio — it is an additional surface for environments where
stdio is not practical (containers, gateways, browsers)."""
from __future__ import annotations

import time
import uuid

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mcp_server import __version__
from mcp_server.core.logging import configure_logging, get_logger
from mcp_server.core.ratelimit import rate_limit
from mcp_server.schemas import (
    SearchDocsInput,
    SqlQueryInput,
    WeatherCoords,
    WeatherForecastInput,
)
from mcp_server.tools.search import search_documents
from mcp_server.tools.sql import list_tables, sql_query
from mcp_server.tools.weather import weather_current, weather_forecast

configure_logging()
log = get_logger("mcp.http")

app = FastAPI(
    title="MCP Server (HTTP transport)",
    version=__version__,
    description=(
        "API-key-authenticated HTTP wrapper exposing the same tools as the stdio "
        "MCP server. Per-key token-bucket rate limiting."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.perf_counter()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        path=request.url.path,
        method=request.method,
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        log.exception("unhandled", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "internal server error", "request_id": request_id},
        )
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["x-request-id"] = request_id
    response.headers["x-response-time-ms"] = f"{elapsed_ms:.1f}"
    log.info("request", status=response.status_code, elapsed_ms=round(elapsed_ms, 1))
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/tools")
async def tools() -> dict[str, list[dict]]:
    return {
        "tools": [
            {"name": "sql_query", "input_schema": SqlQueryInput.model_json_schema()},
            {"name": "list_tables", "input_schema": {"type": "object", "properties": {}}},
            {"name": "weather_current", "input_schema": WeatherCoords.model_json_schema()},
            {"name": "weather_forecast", "input_schema": WeatherForecastInput.model_json_schema()},
            {"name": "search_documents", "input_schema": SearchDocsInput.model_json_schema()},
        ]
    }


def _safe_call(coro):  # type: ignore[no-untyped-def]
    async def _wrapped():
        try:
            return await coro
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _wrapped()


@app.post("/tools/sql_query")
async def http_sql_query(
    params: SqlQueryInput,
    _: str = Depends(rate_limit),
):
    return await _safe_call(sql_query(params))


@app.post("/tools/list_tables")
async def http_list_tables(_: str = Depends(rate_limit)):
    return await list_tables()


@app.post("/tools/weather_current")
async def http_weather_current(params: WeatherCoords, _: str = Depends(rate_limit)):
    return await weather_current(params)


@app.post("/tools/weather_forecast")
async def http_weather_forecast(params: WeatherForecastInput, _: str = Depends(rate_limit)):
    return await weather_forecast(params)


@app.post("/tools/search_documents")
async def http_search_documents(params: SearchDocsInput, _: str = Depends(rate_limit)):
    return await _safe_call(search_documents(params))
