from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from mcp_server.core.config import settings


class SqlSafetyError(ValueError):
    """Raised when a user-supplied query violates the sandbox rules."""


# Anything that mutates schema or session state — even if smuggled into a CTE.
_BANNED_TOKENS = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|"
    r"COPY|VACUUM|ANALYZE|REINDEX|CLUSTER|LOCK|COMMENT|SET|RESET|"
    r"CALL|DO|NOTIFY|LISTEN|UNLISTEN|EXPLAIN\s+ANALYZE)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SafeQuery:
    sql: str
    limit: int


def validate_query(raw: str, *, requested_limit: int | None = None) -> SafeQuery:
    """Sandbox a user-supplied SQL string.

    Layered defenses:
    1. Length cap (cheap DoS protection).
    2. Token-level scan for write/DDL keywords.
    3. Parse with sqlglot. The top-level must be a SELECT or a WITH-of-SELECT.
    4. Reject multiple statements.
    5. Enforce a LIMIT — append one if missing.

    Even if all of this fails, the connection itself is a read-only role with
    `default_transaction_read_only=on` and a statement_timeout, so attempts to
    write would still be rejected at the DB.
    """
    if not raw or not raw.strip():
        raise SqlSafetyError("empty query")
    if len(raw) > settings.sql_max_query_len:
        raise SqlSafetyError(f"query exceeds max length of {settings.sql_max_query_len} chars")

    if _BANNED_TOKENS.search(raw):
        raise SqlSafetyError("query contains forbidden keyword (write/DDL/session-mutation)")

    try:
        statements = sqlglot.parse(raw, read="postgres")
    except sqlglot.errors.ParseError as exc:
        raise SqlSafetyError(f"parse error: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SqlSafetyError("only a single statement is allowed")

    stmt = statements[0]
    if not isinstance(stmt, (exp.Select, exp.Subquery, exp.Union, exp.With)):
        raise SqlSafetyError(f"only SELECT/CTE statements are allowed (got {type(stmt).__name__})")

    if isinstance(stmt, exp.With) and not isinstance(stmt.this, (exp.Select, exp.Union)):
        raise SqlSafetyError("CTE must wrap a SELECT")

    requested = requested_limit if requested_limit is not None else settings.sql_max_rows
    enforced = min(max(1, requested), settings.sql_max_rows)

    existing = stmt.args.get("limit") if hasattr(stmt, "args") else None
    if existing is None:
        stmt = stmt.limit(enforced)
    else:
        try:
            existing_val = int(existing.expression.this)
            if existing_val > enforced:
                stmt = stmt.limit(enforced)
        except (AttributeError, ValueError, TypeError):
            stmt = stmt.limit(enforced)

    return SafeQuery(sql=stmt.sql(dialect="postgres"), limit=enforced)
