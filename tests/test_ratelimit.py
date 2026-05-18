from __future__ import annotations

import asyncio

import pytest

from mcp_server.core.ratelimit import TokenBucketLimiter


async def test_allows_up_to_capacity() -> None:
    bucket = TokenBucketLimiter(capacity=3, refill_per_sec=0.0001)
    for _ in range(3):
        ok, _ = await bucket.take("k1")
        assert ok


async def test_rejects_after_capacity() -> None:
    bucket = TokenBucketLimiter(capacity=2, refill_per_sec=0.0001)
    assert (await bucket.take("k1"))[0]
    assert (await bucket.take("k1"))[0]
    ok, retry = await bucket.take("k1")
    assert not ok
    assert retry > 0


async def test_refills_over_time() -> None:
    bucket = TokenBucketLimiter(capacity=1, refill_per_sec=50.0)
    assert (await bucket.take("k1"))[0]
    assert (await bucket.take("k1"))[0] is False
    await asyncio.sleep(0.04)
    assert (await bucket.take("k1"))[0]


async def test_isolated_per_key() -> None:
    bucket = TokenBucketLimiter(capacity=1, refill_per_sec=0.0001)
    assert (await bucket.take("a"))[0]
    assert (await bucket.take("a"))[0] is False
    assert (await bucket.take("b"))[0]


@pytest.mark.parametrize("capacity,refill", [(10, 1.0), (1, 100.0), (60, 1.0)])
async def test_never_exceeds_capacity(capacity: int, refill: float) -> None:
    bucket = TokenBucketLimiter(capacity=capacity, refill_per_sec=refill)
    await asyncio.sleep(0.05)
    successes = 0
    for _ in range(capacity + 10):
        ok, _ = await bucket.take("k")
        if ok:
            successes += 1
    assert successes <= capacity + 1  # +1 accounts for tiny refill during the burst
