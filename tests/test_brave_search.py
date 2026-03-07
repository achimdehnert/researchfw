"""Tests for BraveSearchService."""
import httpx
import pytest
import respx

from iil_researchfw.core.exceptions import RateLimitError
from iil_researchfw.search.brave import BraveSearchService

BRAVE_RESPONSE = {
    "web": {"results": [{
        "title": "Python Async Guide",
        "url": "https://example.com/async",
        "description": "Best practices for async Python.",
    }]}
}


@pytest.mark.asyncio
async def test_search_returns_results():
    with respx.mock:
        respx.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=httpx.Response(200, json=BRAVE_RESPONSE)
        )
        results = await BraveSearchService(api_key="test-key").search("Python async")
    assert len(results) == 1
    assert results[0].title == "Python Async Guide"
    assert results[0].domain == "example.com"


@pytest.mark.asyncio
async def test_no_api_key_returns_empty():
    results = await BraveSearchService(api_key="").search("test")
    assert results == []


@pytest.mark.asyncio
async def test_rate_limit_raises():
    with respx.mock:
        respx.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=httpx.Response(429)
        )
        with pytest.raises(RateLimitError):
            await BraveSearchService(api_key="key").search("test")
