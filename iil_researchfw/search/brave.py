"""Brave Search API — async web search provider."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from iil_researchfw.core.exceptions import APIError, RateLimitError
from iil_researchfw.search.base import AsyncBaseSearchProvider

logger = logging.getLogger(__name__)

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_LOCAL_URL = "https://api.search.brave.com/res/v1/local/pois"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    domain: str = ""
    age: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class BraveSearchService(AsyncBaseSearchProvider):
    """
    Brave Search API client.

    API-Key via constructor or BRAVE_API_KEY environment variable.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("BRAVE_API_KEY", "")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    async def search(
        self,
        query: str,
        count: int = 10,
        country: str = "de",
        language: str = "de",
        **kwargs: Any,
    ) -> list[SearchResult]:
        """Web search via Brave Search API."""
        if not self.api_key:
            logger.warning("BRAVE_API_KEY not set — returning empty results")
            return []

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }
        params = {"q": query, "count": min(count, 20), "country": country, "search_lang": language}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(BRAVE_SEARCH_URL, headers=headers, params=params)
            if response.status_code == 429:
                raise RateLimitError("brave", 429, "Rate limit exceeded")
            if response.status_code != 200:
                raise APIError("brave", response.status_code, response.text[:200])
            response.raise_for_status()

        return self._parse_results(response.json())

    async def local_search(
        self,
        query: str,
        location: str = "",
        count: int = 5,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """Local business/POI search via Brave Local API."""
        if not self.api_key:
            return []

        headers = {"Accept": "application/json", "X-Subscription-Token": self.api_key}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                BRAVE_LOCAL_URL,
                headers=headers,
                params={"q": f"{query} {location}".strip(), "count": min(count, 20)},
            )
            if response.status_code == 429:
                raise RateLimitError("brave_local", 429)
            response.raise_for_status()
        return self._parse_results(response.json())

    def _parse_results(self, data: dict[str, Any]) -> list[SearchResult]:
        results = []
        for item in data.get("web", {}).get("results", []):
            url = item.get("url", "")
            domain = url.split("/")[2] if url.startswith("http") else ""
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=url,
                    snippet=item.get("description", ""),
                    domain=domain,
                    age=item.get("age", ""),
                )
            )
        return results
