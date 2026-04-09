"""Tests for TTLCache."""
import time

from iil_researchfw._internal.cache import TTLCache


def test_set_and_get():
    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"


def test_miss_returns_none():
    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    assert cache.get("nonexistent") is None


def test_expiry():
    cache: TTLCache[str] = TTLCache(ttl_seconds=0)
    cache.set("key1", "value1")
    time.sleep(0.01)
    assert cache.get("key1") is None


def test_invalidate():
    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    cache.set("key1", "value1")
    cache.invalidate("key1")
    assert cache.get("key1") is None


def test_clear():
    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.clear()
    assert cache.get("k1") is None


def test_make_key_deterministic():
    k1 = TTLCache.make_key("query", ["arxiv"], 10)
    k2 = TTLCache.make_key("query", ["arxiv"], 10)
    assert k1 == k2


def test_make_key_different():
    assert TTLCache.make_key("q1", 10) != TTLCache.make_key("q2", 10)


def test_max_size_evicts_lru():
    """When cache exceeds max_size, oldest (LRU) entry is evicted."""
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_size=3)
    cache.set("a", "1")
    cache.set("b", "2")
    cache.set("c", "3")
    assert cache.size == 3
    cache.set("d", "4")
    assert cache.size == 3
    assert cache.get("a") is None
    assert cache.get("d") == "4"


def test_max_size_lru_order_updated_on_get():
    """Accessing an entry makes it most-recently-used, protecting it from eviction."""
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_size=3)
    cache.set("a", "1")
    cache.set("b", "2")
    cache.set("c", "3")
    cache.get("a")
    cache.set("d", "4")
    assert cache.get("a") == "1"
    assert cache.get("b") is None


def test_evict_expired_cleans_stale():
    """_evict_expired removes all expired entries in one pass."""
    cache: TTLCache[str] = TTLCache(ttl_seconds=0, max_size=100)
    cache.set("a", "1")
    cache.set("b", "2")
    time.sleep(0.01)
    evicted = cache._evict_expired()
    assert evicted == 2
    assert cache.size == 0


def test_set_prefers_expired_eviction_over_lru():
    """When over max_size, expired entries are cleaned first before LRU eviction."""
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_size=2)
    cache.set("a", "1")
    cache.set("b", "2")
    cache._store["a"] = ("1", time.monotonic() - 1)
    cache.set("c", "3")
    assert cache.get("a") is None
    assert cache.get("b") == "2"
    assert cache.get("c") == "3"


def test_size_property():
    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    assert cache.size == 0
    cache.set("a", "1")
    assert cache.size == 1
    cache.set("b", "2")
    assert cache.size == 2
    cache.invalidate("a")
    assert cache.size == 1
