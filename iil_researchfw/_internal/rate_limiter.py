"""Token-bucket rate limiter for external API calls."""
from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """
    Async token-bucket rate limiter.

    Usage::

        limiter = RateLimiter(calls_per_second=3.0)
        async with limiter:
            response = await client.get(...)
    """

    def __init__(self, calls_per_second: float = 1.0) -> None:
        self.calls_per_second = calls_per_second
        self._min_interval = 1.0 / calls_per_second
        self._last_call: float = 0.0
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> RateLimiter:
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()
        return self

    async def __aexit__(self, *_: object) -> None:
        pass
