from __future__ import annotations

import time
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text

from mcp_server.core.logging import get_logger
from mcp_server.core.sql_sandbox import SqlSafetyError, validate_query
from mcp_server.db import readonly_engine
from mcp_server.schemas import ListTablesResult, SqlQueryInput, SqlQueryResult

log = get_logger(__name__)


def _coerce(v: Any) -> Any:
    """Make rows JSON-serializable for the MCP transport (UUID, datetime, Decimal)."""
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, Decimal):
        return float(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


async def sql_query(params: SqlQueryInput) -> SqlQueryResult:
    """Run a sandboxed read-only SQL query against the application database."""
    try:
        safe = validate_query(params.query, requested_limit=params.limit)
    except SqlSafetyError as exc:
        raise ValueError(f"unsafe query: {exc}") from exc

    log.info("sql_query", limit=safe.limit, len=len(safe.sql))
    start = time.perf_counter()

    async with readonly_engine.begin() as conn:
        result = await conn.execute(text(safe.sql))
        keys = list(result.keys())
        rows = [
            {k: _coerce(v) for k, v in zip(keys, row, strict=True)}
            for row in result.fetchall()
        ]

    elapsed = (time.perf_counter() - start) * 1000
    return SqlQueryResult(
        rows=rows,
        row_count=len(rows),
        truncated=len(rows) >= safe.limit,
        elapsed_ms=round(elapsed, 2),
    )


async def list_tables() -> ListTablesResult:
    """List the tables visible to the read-only role in the public schema."""
    sql = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name
    """
    async with readonly_engine.begin() as conn:
        rows = (await conn.execute(text(sql))).fetchall()
    return ListTablesResult(tables=[r[0] for r in rows])
