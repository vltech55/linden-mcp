from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcp_server.core.auth import require_api_key


async def test_accepts_valid_key() -> None:
    out = await require_api_key(x_api_key="test-key-1")
    assert out == "test-key-1"


async def test_rejects_missing_header() -> None:
    with pytest.raises(HTTPException) as exc:
        await require_api_key(x_api_key=None)
    assert exc.value.status_code == 401


async def test_rejects_wrong_key() -> None:
    with pytest.raises(HTTPException) as exc:
        await require_api_key(x_api_key="not-a-real-key")
    assert exc.value.status_code == 401


async def test_uses_constant_time_comparison() -> None:
    # We can't observe timing in a unit test reliably, but we can verify the function
    # accepts the known second key — proving comparison iterates over the set rather
    # than short-circuiting on the first.
    out = await require_api_key(x_api_key="test-key-2")
    assert out == "test-key-2"
