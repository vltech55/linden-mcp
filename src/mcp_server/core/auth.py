from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from mcp_server.core.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """FastAPI dependency: 401 if the header is missing or doesn't match a configured key.

    If MCP_API_KEYS is empty, authentication is disabled (dev only). We log nothing here
    intentionally — that's the HTTP middleware's job, so we don't double-log on every request.
    """
    keys = settings.api_key_set
    if not keys:
        return "dev-no-auth"
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing X-API-Key header",
        )
    for k in keys:
        if hmac.compare_digest(x_api_key, k):
            return k
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid API key",
    )
