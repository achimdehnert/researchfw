"""Token-bucket rate limiter for external API calls."""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """
    Async token-bucket rate limiter.

    Serialises calls made *through the same instance*: each ``async with``
    blocks until at least the configured minimum interval has passed since
    the previous call was let through. Use one instance per rate-limited
    resource (e.g. per external API) — sharing one instance across
    concurrent callers is what makes "at most 1 request every N seconds"
    hold even when those callers run concurrently (``asyncio.gather``).

    Usage::

        limiter = RateLimiter(calls_per_second=3.0)
        async with limiter:
            response = await client.get(...)

    Or directly by minimum interval in seconds (used by
    ``AcademicSearchService`` for per-source throttling, writing-hub#1261 K2)::

        limiter = RateLimiter(min_interval_seconds=3.0)  # arXiv: max 1 req / 3s
        limiter = RateLimiter(min_interval_seconds=0.0)  # no throttling
    """

    def __init__(
        self,
        calls_per_second: float = 1.0,
        *,
        min_interval_seconds: float | None = None,
    ) -> None:
        if min_interval_seconds is not None:
            if min_interval_seconds < 0:
                raise ValueError("min_interval_seconds must be >= 0")
            self._min_interval = min_interval_seconds
            self.calls_per_second = (
                1.0 / min_interval_seconds if min_interval_seconds > 0 else float("inf")
            )
        else:
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
