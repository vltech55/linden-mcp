"""MCP server with stdio transport — point Claude Desktop at this entrypoint.

Tools registered:
    sql_query, list_tables, weather_current, weather_forecast, search_documents

Resources:
    db://schema   — JSON description of public tables visible to the read-only role
    docs://list   — JSON list of indexed documents

The HTTP/SSE transport lives in `http_server.py` (FastAPI). Both share the same
tool implementations from `mcp_server.tools.*` so the surface stays consistent.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from mcp_server import __version__
from mcp_server.core.logging import configure_logging, get_logger
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
log = get_logger("mcp.stdio")

server: Server = Server("mcp-server")


@server.list_tools()
async def _list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="sql_query",
            description=(
                "Run a read-only SELECT against the application database. "
                "INSERT/UPDATE/DELETE/DDL are rejected; queries have a 5s timeout "
                "and are auto-LIMITed."
            ),
            inputSchema=SqlQueryInput.model_json_schema(),
        ),
        types.Tool(
            name="list_tables",
            description="List tables visible to the read-only role in the public schema.",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        types.Tool(
            name="weather_current",
            description="Current weather at the given coordinates (Open-Meteo, no key required).",
            inputSchema=WeatherCoords.model_json_schema(),
        ),
        types.Tool(
            name="weather_forecast",
            description="Daily weather forecast for 1-14 days at the given coordinates.",
            inputSchema=WeatherForecastInput.model_json_schema(),
        ),
        types.Tool(
            name="search_documents",
            description="Semantic search over the indexed documents (pgvector cosine).",
            inputSchema=SearchDocsInput.model_json_schema(),
        ),
    ]


_DISPATCH = {
    "sql_query": lambda args: sql_query(SqlQueryInput.model_validate(args)),
    "list_tables": lambda args: list_tables(),
    "weather_current": lambda args: weather_current(WeatherCoords.model_validate(args)),
    "weather_forecast": lambda args: weather_forecast(WeatherForecastInput.model_validate(args)),
    "search_documents": lambda args: search_documents(SearchDocsInput.model_validate(args)),
}


@server.call_tool()
async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    args = arguments or {}
    handler = _DISPATCH.get(name)
    if handler is None:
        return [types.TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]
    try:
        result = await handler(args)
    except Exception as exc:
        log.exception("tool_failed", tool=name, error=str(exc))
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": type(exc).__name__, "detail": str(exc)}),
            )
        ]
    payload = result.model_dump_json() if hasattr(result, "model_dump_json") else json.dumps(result)
    return [types.TextContent(type="text", text=payload)]


@server.list_resources()
async def _list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri=types.AnyUrl("db://schema"),
            name="Database schema",
            description="JSON listing of tables and columns visible to the read-only role.",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def _read_resource(uri: types.AnyUrl) -> str:
    s = str(uri)
    if s == "db://schema":
        return json.dumps((await list_tables()).model_dump())
    raise ValueError(f"unknown resource: {s}")


async def main() -> None:
    log.info("mcp_stdio_start", version=__version__)
    async with mcp.server.stdio.stdio_server() as (reader, writer):
        await server.run(
            reader,
            writer,
            InitializationOptions(
                server_name="mcp-server",
                server_version=__version__,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
