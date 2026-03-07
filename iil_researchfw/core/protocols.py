"""Central Protocol definitions for iil-researchfw."""
from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncIterator, Protocol, runtime_checkable

from iil_researchfw.core.models import Finding, Source


class LLMCallable(Protocol):
    """Async LLM callable — inject into AISummaryService."""

    async def __call__(
        self,
        prompt: str,
        max_tokens: int = 500,
        response_format: dict[str, Any] | None = None,
    ) -> str: ...


class AsyncLLMStreamCallable(Protocol):
    """Streaming LLM callable."""

    async def __call__(self, prompt: str) -> AsyncIterator[str]: ...


@runtime_checkable
class ResearchProjectProtocol(Protocol):
    """Protocol for Django ResearchProject models — avoids ORM coupling."""

    name: str
    query: str
    description: str
    created_at: datetime

    @property
    def findings(self) -> list[Finding]: ...

    @property
    def sources(self) -> list[Source]: ...
