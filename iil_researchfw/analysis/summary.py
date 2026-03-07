"""AI-powered research summary — LLM-agnostic via Protocol injection."""
from __future__ import annotations

import logging
from typing import Any

from iil_researchfw.core.protocols import LLMCallable

logger = logging.getLogger(__name__)


class AISummaryService:
    """
    LLM-agnostic summary service.

    Inject any async callable matching LLMCallable Protocol.
    Falls back to extractive summaries when llm_fn is None.
    """

    def __init__(self, llm_fn: LLMCallable | None = None) -> None:
        self._llm_fn = llm_fn

    async def summarize_findings(
        self,
        findings: list[dict[str, Any]],
        max_length: int = 500,
        style: str = "academic",
    ) -> dict[str, Any]:
        """Summarize research findings. Styles: academic, executive, bullet_points."""
        if not findings:
            return {"summary": "", "key_points": [], "ai_generated": False}
        if self._llm_fn:
            return await self._llm_summarize(findings, max_length, style)
        return self._extractive_summarize(findings)

    async def summarize_sources(
        self, sources: list[dict[str, Any]], max_length: int = 300
    ) -> dict[str, Any]:
        """Thematic analysis of sources."""
        if not sources:
            return {"summary": "", "themes": [], "ai_generated": False}
        if self._llm_fn:
            titles = [s.get("title", "") for s in sources[:20]]
            prompt = (
                f"Analyse the following {len(sources)} research sources thematically.\n"
                f"Sources: {', '.join(titles)}\n"
                f"Provide: main themes, key topics, research gaps in {max_length} words."
            )
            text = await self._llm_fn(prompt, max_tokens=max_length * 2)
            return {"summary": text.strip(), "themes": [], "ai_generated": True}
        return {"summary": f"Analysis of {len(sources)} sources.", "themes": [], "ai_generated": False}

    async def extract_key_points(self, text: str, max_points: int = 5) -> list[str]:
        """Extract key points from text."""
        if self._llm_fn:
            prompt = (
                f"Extract exactly {max_points} key points from the following text.\n"
                f"Format: one point per line, starting with '- '\n\n{text[:3000]}"
            )
            result = await self._llm_fn(prompt, max_tokens=300)
            points = [line.lstrip("- ").strip() for line in result.strip().splitlines() if line.strip()]
            return points[:max_points]
        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
        return sentences[:max_points]

    async def generate_research_questions(self, topic: str, count: int = 5) -> list[str]:
        """Generate research questions for a topic."""
        if self._llm_fn:
            prompt = (
                f"Generate {count} specific research questions about: {topic}\n"
                f"Format: one question per line, starting with a question word."
            )
            result = await self._llm_fn(prompt, max_tokens=400)
            lines = [line.strip() for line in result.strip().splitlines() if line.strip()]
            return [line.lstrip("0123456789. ") for line in lines][:count]
        return [
            f"What are the key aspects of {topic}?",
            f"How has {topic} evolved recently?",
            f"What are the main challenges in {topic}?",
            f"Who are the leading researchers in {topic}?",
            f"What are the future directions for {topic}?",
        ][:count]

    async def _llm_summarize(
        self, findings: list[dict[str, Any]], max_length: int, style: str
    ) -> dict[str, Any]:
        assert self._llm_fn is not None
        style_instruction = {
            "academic": "formal academic style with citations",
            "executive": "executive summary, 3-5 bullet points",
            "bullet_points": "structured bullet points with headers",
        }.get(style, "clear and concise")
        content = "\n".join(
            f"- {f.get('title', '')}: {f.get('content', '')[:200]}" for f in findings[:20]
        )
        prompt = (
            f"Summarize the following research findings in {style_instruction},"
            f" approximately {max_length} words:\n\n{content}"
        )
        summary = await self._llm_fn(prompt, max_tokens=max_length * 2)
        key_points = await self.extract_key_points(summary, max_points=5)
        return {
            "summary": summary.strip(), "key_points": key_points,
            "style": style, "ai_generated": True, "source_count": len(findings),
        }

    def _extractive_summarize(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        key_points = [f.get("title", f.get("content", "")[:100]) for f in findings[:5]]
        return {
            "summary": "Key findings: " + "; ".join(key_points[:3]) + ".",
            "key_points": key_points, "style": "extractive",
            "ai_generated": False, "source_count": len(findings),
        }
