"""In-memory TTL cache for research results."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """
    Simple in-memory TTL cache.

    Usage::

        cache: TTLCache[list[AcademicPaper]] = TTLCache(ttl_seconds=3600)
        key = TTLCache.make_key(query, sources)
        if cached := cache.get(key):
            return cached
        result = await expensive_call()
        cache.set(key, result)
        return result
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._store: dict[str, tuple[T, float]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> T | None:
        if entry := self._store.get(key):
            value, expires_at = entry
            if time.monotonic() < expires_at:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: T) -> None:
        self._store[key] = (value, time.monotonic() + self._ttl)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    @staticmethod
    def make_key(*args: Any) -> str:
        raw = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
