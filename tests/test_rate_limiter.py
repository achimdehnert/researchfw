"""Tests for RateLimiter."""
import time

import pytest

from iil_researchfw._internal.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_first_call_fast():
    limiter = RateLimiter(calls_per_second=10.0)
    start = time.monotonic()
    async with limiter:
        pass
    assert time.monotonic() - start < 0.5


@pytest.mark.asyncio
async def test_rate_limiter_enforces_delay():
    limiter = RateLimiter(calls_per_second=2.0)
    async with limiter:
        pass
    start = time.monotonic()
    async with limiter:
        pass
    assert time.monotonic() - start >= 0.4
