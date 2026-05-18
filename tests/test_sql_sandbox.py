from __future__ import annotations

import pytest

from mcp_server.core.sql_sandbox import SqlSafetyError, validate_query


def test_select_accepted_and_limit_appended() -> None:
    out = validate_query("SELECT * FROM customers", requested_limit=10)
    assert "LIMIT 10" in out.sql.upper()
    assert out.limit == 10


def test_existing_limit_lower_is_preserved() -> None:
    out = validate_query("SELECT * FROM customers LIMIT 3", requested_limit=100)
    assert "LIMIT 3" in out.sql.upper()


def test_existing_limit_above_cap_is_clamped() -> None:
    out = validate_query("SELECT * FROM customers LIMIT 99999", requested_limit=100)
    assert "LIMIT 100" in out.sql.upper()


@pytest.mark.parametrize(
    "bad",
    [
        "UPDATE customers SET name='x'",
        "DELETE FROM customers",
        "INSERT INTO customers (name) VALUES ('x')",
        "DROP TABLE customers",
        "ALTER TABLE customers ADD COLUMN x text",
        "TRUNCATE customers",
        "GRANT ALL ON customers TO public",
        "CREATE TABLE foo (id int)",
        "VACUUM customers",
    ],
)
def test_write_keywords_rejected(bad: str) -> None:
    with pytest.raises(SqlSafetyError):
        validate_query(bad)


def test_multiple_statements_rejected() -> None:
    with pytest.raises(SqlSafetyError):
        validate_query("SELECT 1; SELECT 2")


def test_empty_query_rejected() -> None:
    with pytest.raises(SqlSafetyError):
        validate_query("   ")


def test_too_long_rejected() -> None:
    with pytest.raises(SqlSafetyError):
        validate_query("SELECT '" + "x" * 5000 + "'")


def test_cte_select_accepted() -> None:
    out = validate_query(
        "WITH recent AS (SELECT * FROM orders ORDER BY placed_at DESC LIMIT 50) "
        "SELECT * FROM recent"
    )
    assert "LIMIT" in out.sql.upper()


def test_cte_with_update_rejected() -> None:
    # Sneaky DML hidden in a CTE — the token-level guard catches it before parsing.
    with pytest.raises(SqlSafetyError):
        validate_query(
            "WITH x AS (UPDATE customers SET name='x' RETURNING id) SELECT * FROM x"
        )
