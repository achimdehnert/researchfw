"""Abstract base class for async search providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AsyncBaseSearchProvider(ABC):
    """Base class for all search providers in iil-researchfw."""

    @abstractmethod
    async def search(self, query: str, **kwargs: Any) -> list[Any]:
        """Execute a search and return results."""
        ...
