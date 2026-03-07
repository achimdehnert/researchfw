"""AI-powered research summary — LLM-agnostic via Protocol injection."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

from iil_researchfw.core.protocols import LLMCallable

logger = logging.getLogger(__name__)

# Citation style additions for scientific summaries
_CITATION_INSTRUCTIONS: dict[str, str] = {
    "none": "",
    "inline": (
        "Zitiere Quellen direkt im Text als Kurzreferenz in eckigen Klammern, "
        "z.B. [Smith 2023] oder [arXiv:2401.12345]. "
        "Füge KEINE separate Literaturliste hinzu."
    ),
    "bibliography": (
        "Verwende keine Inline-Zitate im Fließtext. "
        "Füge am Ende einen Abschnitt **Literatur** hinzu mit nummerierten Einträgen:\n"
        "[1] Titel — Autoren (Jahr) — Quelle/DOI\n"
        "[2] ...\n"
        "Referenziere im Text nur mit Nummern wie [1], [2]."
    ),
}


_STYLE_INSTRUCTIONS: dict[str, str] = {
    # Original styles
    "academic": "formal academic style with citations",
    "executive": "executive summary, 3-5 bullet points",
    "bullet_points": "structured bullet points with headers",
    # Research-level styles — enforce markdown structure
    "simple": (
        "Schreibe auf Deutsch in einfacher, allgemeinverständlicher Sprache für einen "
        "interessierten Laien. Vermeide Fachbegriffe.\n\n"
        "Format — gib NUR dieses Markdown aus, keine Einleitung:\n"
        "**Was wurde herausgefunden?**\n"
        "Ein kurzer Satz als Einstieg.\n\n"
        "**Die wichtigsten Punkte:**\n"
        "- Punkt 1\n- Punkt 2\n- Punkt 3\n\n"
        "**Was bedeutet das?**\n"
        "Ein abschließender Satz in einfacher Sprache. Maximal 120 Wörter gesamt."
    ),
    "medium": (
        "Schreibe auf Deutsch für einen informierten Leser mit allgemeinem Hintergrundwissen.\n\n"
        "Format — gib NUR dieses Markdown aus, keine Einleitung:\n"
        "**Kernaussage**\n"
        "1-2 Sätze zur zentralen Erkenntnis.\n\n"
        "**Wichtigste Erkenntnisse**\n"
        "- Erkenntnis 1\n- Erkenntnis 2\n- Erkenntnis 3\n\n"
        "**Einordnung**\n"
        "1-2 Sätze zur Bedeutung und zu offenen Fragen. Maximal 180 Wörter gesamt."
    ),
    "complex": (
        "Schreibe auf Deutsch für ein Fachpublikum. Gehe auf Nuancen und Widersprüche ein.\n\n"
        "Format — gib NUR dieses Markdown aus, keine Einleitung:\n"
        "**Haupterkenntnisse**\n"
        "2-3 Sätze zu den zentralen Befunden.\n\n"
        "**Detailanalyse**\n"
        "- Aspekt 1 mit Kontext\n- Aspekt 2 mit Kontext\n- Aspekt 3 mit Kontext\n\n"
        "**Kritische Einordnung**\n"
        "Widersprüche, Limitationen oder offene Forschungsfragen.\n\n"
        "**Fazit**\n"
        "Schlussfolgerung in 1-2 Sätzen. Maximal 280 Wörter gesamt."
    ),
    "scientific": (
        "Schreibe auf Deutsch eine wissenschaftliche Zusammenfassung im Abstract-Stil.\n\n"
        "Format — gib NUR dieses Markdown aus, keine Einleitung:\n"
        "**Fragestellung**\n"
        "Forschungsfrage und Relevanz.\n\n"
        "**Methodik & Quellen**\n"
        "Datengrundlage und verwendete Quellen.\n\n"
        "**Ergebnisse**\n"
        "- Befund 1\n- Befund 2\n- Befund 3\n\n"
        "**Schlussfolgerung**\n"
        "Wissenschaftliche Einordnung und Implikationen. Maximal 320 Wörter gesamt."
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
        for attempt in range(3):
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
                if resp.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
        return ""

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
        citation_style: str = "none",
    ) -> dict[str, Any]:
        """Summarize research findings.

        Styles: simple, medium, complex, scientific (research levels)
        or: academic, executive, bullet_points (classic styles).

        citation_style: 'none' | 'inline' | 'bibliography'
          - 'inline'      — [Author Year] refs in text, no separate list
          - 'bibliography'— numbered refs [1] + **Literatur** section at end
          Only applied when style='scientific' (ignored otherwise).
        """
        if not findings:
            return {"summary": "", "key_points": [], "ai_generated": False}
        if self._llm_fn:
            return await self._llm_summarize(
                findings, max_length, style, citation_style
            )
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
        self,
        findings: list[dict[str, Any]],
        max_length: int,
        style: str,
        citation_style: str = "none",
    ) -> dict[str, Any]:
        if self._llm_fn is None:
            return self._extractive_summarize(findings)
        style_instruction = _STYLE_INSTRUCTIONS.get(style, _STYLE_INSTRUCTIONS["medium"])
        # Citation instructions only make sense for scientific style
        cite_instruction = ""
        if style == "scientific" and citation_style != "none":
            cite_instruction = (
                "\n\n" + _CITATION_INSTRUCTIONS.get(citation_style, "")
            )
        content = "\n".join(
            f"- {f.get('title', '')}: {f.get('content', '')[:200]}" for f in findings[:20]
        )
        prompt = (
            f"{style_instruction}{cite_instruction}\n\n"
            f"Forschungsergebnisse (Grundlage):\n{content}"
        )
        summary = await self._llm_fn(prompt, max_tokens=max_length * 2)
        key_points = await self.extract_key_points(summary, max_points=5)
        return {
            "summary": summary.strip(),
            "key_points": key_points,
            "style": style,
            "citation_style": citation_style,
            "ai_generated": True,
            "source_count": len(findings),
        }

    def _extractive_summarize(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        key_points = [f.get("title", f.get("content", "")[:100]) for f in findings[:5]]
        return {
            "summary": "Key findings: " + "; ".join(key_points[:3]) + ".",
            "key_points": key_points, "style": "extractive",
            "ai_generated": False, "source_count": len(findings),
        }
