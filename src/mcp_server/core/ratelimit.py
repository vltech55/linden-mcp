from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status

from mcp_server.core.auth import require_api_key
from mcp_server.core.config import settings


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class TokenBucketLimiter:
    """In-memory per-key token bucket. Suitable for a single-process MCP server;
    for horizontal scale, swap the backing store for Redis."""

    def __init__(self, capacity: int, refill_per_sec: float) -> None:
        self.capacity = capacity
        self.refill = refill_per_sec
        self._buckets: dict[str, _Bucket] = {}
        self._lock = asyncio.Lock()

    async def take(self, key: str, *, cost: float = 1.0) -> tuple[bool, float]:
        """Try to take `cost` tokens for `key`. Returns (allowed, retry_after_seconds)."""
        async with self._lock:
            now = time.monotonic()
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket(tokens=self.capacity, last_refill=now)
                self._buckets[key] = b
            elapsed = now - b.last_refill
            b.tokens = min(self.capacity, b.tokens + elapsed * self.refill)
            b.last_refill = now
            if b.tokens >= cost:
                b.tokens -= cost
                return True, 0.0
            retry_after = (cost - b.tokens) / self.refill if self.refill > 0 else 1.0
            return False, retry_after


_limiter = TokenBucketLimiter(
    capacity=settings.rate_limit_tokens,
    refill_per_sec=settings.rate_limit_refill_per_sec,
)


async def rate_limit(key: str = Depends(require_api_key)) -> str:
    """Composed dependency: auth runs first, then rate-limits using the key as the identity."""
    allowed, retry_after = await _limiter.take(key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
            headers={"Retry-After": f"{retry_after:.1f}"},
        )
    return key


# Exposed for tests that need to reset state between cases.
def _reset_buckets() -> None:
    _limiter._buckets.clear()
