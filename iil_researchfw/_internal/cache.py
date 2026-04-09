"""In-memory TTL + LRU cache for research results."""
from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """
    In-memory TTL cache with optional max-size LRU eviction.

    When *max_size* is set, the least-recently-used entry is evicted
    once the cache exceeds the limit.  Expired entries are purged lazily
    on ``get()`` and proactively via ``_evict_expired()`` on ``set()``.

    Usage::

        cache: TTLCache[list[AcademicPaper]] = TTLCache(ttl_seconds=3600, max_size=128)
        key = TTLCache.make_key(query, sources)
        if cached := cache.get(key):
            return cached
        result = await expensive_call()
        cache.set(key, result)
        return result
    """

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 256) -> None:
        self._store: OrderedDict[str, tuple[T, float]] = OrderedDict()
        self._ttl = ttl_seconds
        self._max_size = max_size

    def get(self, key: str) -> T | None:
        if entry := self._store.get(key):
            value, expires_at = entry
            if time.monotonic() < expires_at:
                self._store.move_to_end(key)
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: T) -> None:
        now = time.monotonic()
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, now + self._ttl)
        if len(self._store) > self._max_size:
            self._evict_expired(now)
        if len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        """Current number of entries (including possibly expired)."""
        return len(self._store)

    def _evict_expired(self, now: float | None = None) -> int:
        """Remove all expired entries.  Returns count of evicted items."""
        now = now or time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if exp <= now]
        for k in expired:
            del self._store[k]
        return len(expired)

    @staticmethod
    def make_key(*args: Any) -> str:
        raw = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
