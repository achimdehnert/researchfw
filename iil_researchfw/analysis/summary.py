"""AI-powered research summary — LLM-agnostic via Protocol injection."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from iil_researchfw.core.protocols import LLMCallable

logger = logging.getLogger(__name__)

_STYLE_INSTRUCTIONS: dict[str, str] = {
    # Original styles
    "academic": "formal academic style with citations",
    "executive": "executive summary, 3-5 bullet points",
    "bullet_points": "structured bullet points with headers",
    # Research-level styles
    "simple": (
        "Beantworte auf Deutsch in einfacher, allgemeinverständlicher Sprache. "
        "Vermeide Fachbegriffe. Schreibe so, dass ein interessierter Laie alles versteht. "
        "Maximal 150 Wörter."
    ),
    "medium": (
        "Beantworte auf Deutsch prägnant für einen informierten Leser mit allgemeinem "
        "Hintergrundwissen. Hebe die wichtigsten Erkenntnisse und Zusammenhänge hervor. "
        "Maximal 200 Wörter."
    ),
    "complex": (
        "Erstelle auf Deutsch eine detaillierte Zusammenfassung für ein Fachpublikum. "
        "Gehe auf Nuancen, Widersprüche und offene Fragen ein. "
        "Struktur: Haupterkenntnisse — Kontext — Kritische Einordnung. Maximal 300 Wörter."
    ),
    "scientific": (
        "Erstelle eine wissenschaftliche Zusammenfassung auf Deutsch im Stil eines Abstract. "
        "Formuliere präzise, objektiv und mit korrekter Fachterminologie. "
        "Struktur: Fragestellung — Methodik/Quellen — Ergebnisse — Schlussfolgerung. "
        "Zitiere relevante Quellen nach Titel. Maximal 350 Wörter."
    ),
}


def make_together_llm(
    api_key: str | None = None,
    model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
) -> LLMCallable:
    """
    Factory: returns an async LLMCallable backed by Together AI.

    Usage::

        llm = make_together_llm(api_key=os.environ["TOGETHER_API_KEY"])
        service = AISummaryService(llm_fn=llm)
    """
    key = api_key or os.environ.get("TOGETHER_API_KEY", "")

    async def _call(prompt: str, max_tokens: int = 500, **_: Any) -> str:
        if not key:
            return ""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.4,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

    return _call  # type: ignore[return-value]


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
        style: str = "medium",
    ) -> dict[str, Any]:
        """Summarize research findings.

        Styles: simple, medium, complex, scientific (research levels)
        or: academic, executive, bullet_points (classic styles).
        """
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
        if self._llm_fn is None:
            return self._extractive_summarize(findings)
        style_instruction = _STYLE_INSTRUCTIONS.get(style, _STYLE_INSTRUCTIONS["medium"])
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
