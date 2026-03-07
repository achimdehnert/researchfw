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
