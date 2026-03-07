"""ResearchService — async orchestrator for search + analysis."""
from __future__ import annotations

import logging
from typing import Any

from iil_researchfw.core.models import Finding, ResearchContext, ResearchOutput, Source

logger = logging.getLogger(__name__)


class ResearchService:
    """
    Central research orchestrator.

    Coordinates web search, academic search, finding extraction,
    and optional AI summary generation.
    """

    def __init__(
        self,
        web_search: Any | None = None,
        academic_search: Any | None = None,
        summary_service: Any | None = None,
    ) -> None:
        self._web_search = web_search
        self._academic_search = academic_search
        self._summary_service = summary_service

    async def research(
        self,
        query: str,
        options: dict[str, Any] | None = None,
    ) -> ResearchOutput:
        """Full research workflow: search → extract findings → summarize."""
        ctx = ResearchContext(query=query, **(options or {}))
        output = ResearchOutput(success=False, query=query)

        sources: list[Source] = []
        try:
            sources.extend(await self._web_results(ctx))
            sources.extend(await self._academic_results(ctx))
        except Exception as exc:
            logger.warning("Search error: %s", exc)
            output.errors.append(str(exc))

        output = output.model_copy(update={"sources": sources})
        findings = self._extract_findings(sources, ctx)
        output = output.model_copy(update={"findings": findings})

        if self._summary_service and findings:
            try:
                result = await self._summary_service.summarize_findings(
                    [f.model_dump() for f in findings]
                )
                output = output.model_copy(update={"summary": result.get("summary")})
            except Exception as exc:
                logger.warning("Summary error: %s", exc)

        return output.model_copy(update={"success": True})

    async def quick_search(self, query: str, max_results: int = 5) -> list[Source]:
        """Quick web search, no analysis."""
        ctx = ResearchContext(query=query, max_sources=max_results)
        return await self._web_results(ctx)

    async def fact_check(self, claim: str, sources: int = 3) -> ResearchOutput:
        """Verify a claim against web sources."""
        output = await self.research(f"fact check: {claim}", {"max_sources": sources})
        return output.model_copy(update={"metadata": {**output.metadata, "claim": claim, "type": "fact_check"}})

    async def _web_results(self, ctx: ResearchContext) -> list[Source]:
        if not self._web_search:
            return []
        results = await self._web_search.search(ctx.query, count=ctx.max_sources)
        return [
            Source(url=r.url, title=r.title, snippet=r.snippet, domain=r.domain)
            for r in results
            if hasattr(r, "url")
        ]

    async def _academic_results(self, ctx: ResearchContext) -> list[Source]:
        if not self._academic_search:
            return []
        papers = await self._academic_search.search(ctx.query, max_results=ctx.max_sources)
        return [
            Source(
                url=p.url,
                title=p.title,
                snippet=p.abstract[:200] if p.abstract else "",
                domain=p.source,
            )
            for p in papers
        ]

    def _extract_findings(self, sources: list[Source], ctx: ResearchContext) -> list[Finding]:
        return [
            Finding(
                id=f"finding-{i}",
                title=source.title,
                content=source.snippet,
                source_url=source.url,
                relevance_score=max(0.0, 1.0 - i * 0.05),
            )
            for i, source in enumerate(sources)
            if source.snippet
        ]
