"""Prompts sind injizierbar (writing-hub#1261 K2, ADR-204-Bruecke).

Bis 2026-09-23 waren die LLM-Prompts in ``SmartSearchService`` Modul-Konstanten
und in ``AISummaryService`` inline als f-Strings gebaut — ein Konsument mit
eigener Prompt-Verwaltung (z.B. writing-hub/promptfw-Templates, ADR-204)
konnte sie nicht ersetzen, ohne den Quellcode zu patchen.

Diese Tests belegen zwei Dinge je Dienst:

1. Ohne Injektion ist der erzeugte Prompt byte-identisch zum bisherigen Text
   (Snapshot-Vergleich gegen die alten Modul-Konstanten/f-String-Baupläne).
2. Ein injizierter Prompt (mit denselben Platzhaltern) wird tatsaechlich
   verwendet — die Injektion wirkt, statt nur akzeptiert zu werden.
"""

from __future__ import annotations

import pytest

from iil_researchfw.analysis.summary import AISummaryService, SummaryPrompts
from iil_researchfw.search.academic import AcademicPaper
from iil_researchfw.search.smart import (
    GAP_ANALYSIS_PROMPT,
    QUERY_EXPANSION_PROMPT,
    RELEVANCE_SCORING_PROMPT,
    ScoredPaper,
    SmartSearchPrompts,
    SmartSearchService,
)


class _RecordingLLM:
    """Merkt sich alle gesehenen Prompts (in Reihenfolge), antwortet sonst mit leerem JSON.

    ``summarize_findings`` ruft den LLM zweimal auf (Summary, dann
    ``extract_key_points`` fuer die Kernpunkte) — ``last_prompt`` allein
    wuerde also den ERSTEN (den eigentlich zu pruefenden) Prompt verdecken.
    """

    def __init__(self, response: str = "") -> None:
        self.prompts: list[str] = []
        self.response = response

    @property
    def last_prompt(self) -> str:
        return self.prompts[-1] if self.prompts else ""

    @property
    def first_prompt(self) -> str:
        return self.prompts[0] if self.prompts else ""

    async def __call__(self, prompt: str, max_tokens: int = 500, **_: object) -> str:
        self.prompts.append(prompt)
        return self.response


# --- SmartSearchService: Default byte-identisch ----------------------------


@pytest.mark.asyncio
async def test_should_use_byte_identical_query_expansion_prompt_by_default():
    llm = _RecordingLLM('{"queries": ["q1"]}')
    service = SmartSearchService(llm_fn=llm)
    await service._expand_query("climate change")
    assert llm.last_prompt == QUERY_EXPANSION_PROMPT.format(topic="climate change", max_queries=4)


@pytest.mark.asyncio
async def test_should_use_byte_identical_gap_analysis_prompt_by_default():
    llm = _RecordingLLM('{"queries": ["q1"], "gaps": []}')
    service = SmartSearchService(llm_fn=llm)
    papers = [ScoredPaper(paper=AcademicPaper(title="Paper A"), relevance_score=8.0)]
    await service._analyze_gaps(papers, "climate change")
    expected = GAP_ANALYSIS_PROMPT.format(
        topic="climate change",
        papers_summary="- Paper A (score: 8.0)",
        max_queries=4,
    )
    assert llm.last_prompt == expected


@pytest.mark.asyncio
async def test_should_use_byte_identical_relevance_scoring_prompt_by_default():
    llm = _RecordingLLM("[]")
    service = SmartSearchService(llm_fn=llm)
    papers = [AcademicPaper(title="Paper A", source="arxiv")]
    await service._score_batch(papers, "climate change")
    assert "Rate each paper's relevance" in llm.last_prompt
    # Der komplette Aufbau muss zur alten Konstante passen -- nicht nur ein Ausschnitt.
    import json

    papers_for_prompt = [
        {
            "index": 0,
            "title": "Paper A",
            "abstract": "",
            "authors": "",
            "source": "arxiv",
            "year": "",
        }
    ]
    expected = RELEVANCE_SCORING_PROMPT.format(
        topic="climate change",
        papers_json=json.dumps(papers_for_prompt, ensure_ascii=False, indent=2),
    )
    assert llm.last_prompt == expected


# --- SmartSearchService: Injektion wirkt ------------------------------------


@pytest.mark.asyncio
async def test_should_use_injected_query_expansion_prompt():
    custom = SmartSearchPrompts(
        query_expansion="CUSTOM-PROMPTFW topic={topic} n={max_queries}",
    )
    llm = _RecordingLLM('{"queries": ["q1"]}')
    service = SmartSearchService(llm_fn=llm, prompts=custom, max_queries=2)
    await service._expand_query("solar energy")
    assert llm.last_prompt == "CUSTOM-PROMPTFW topic=solar energy n=2"


@pytest.mark.asyncio
async def test_should_use_injected_relevance_scoring_prompt():
    custom = SmartSearchPrompts(relevance_scoring="SCORE {topic} :: {papers_json}")
    llm = _RecordingLLM("[]")
    service = SmartSearchService(llm_fn=llm, prompts=custom)
    papers = [AcademicPaper(title="Paper A", source="arxiv")]
    await service._score_batch(papers, "solar energy")
    assert llm.last_prompt.startswith("SCORE solar energy :: [")


# --- AISummaryService: Default byte-identisch -------------------------------


@pytest.mark.asyncio
async def test_should_use_byte_identical_sources_analysis_prompt_by_default():
    llm = _RecordingLLM("Thematic analysis.")
    service = AISummaryService(llm_fn=llm)
    sources = [{"title": "Paper A"}, {"title": "Paper B"}]
    await service.summarize_sources(sources, max_length=300)
    expected = (
        f"Analyse the following {len(sources)} research sources thematically.\n"
        f"Sources: {', '.join(s['title'] for s in sources)}\n"
        f"Provide: main themes, key topics, research gaps in 300 words."
    )
    assert llm.last_prompt == expected


@pytest.mark.asyncio
async def test_should_use_byte_identical_key_points_prompt_by_default():
    llm = _RecordingLLM("- a\n- b")
    service = AISummaryService(llm_fn=llm)
    await service.extract_key_points("Some long text.", max_points=3)
    expected = (
        "Extract exactly 3 key points from the following text.\n"
        "Format: one point per line, starting with '- '\n\nSome long text."
    )
    assert llm.last_prompt == expected


@pytest.mark.asyncio
async def test_should_use_byte_identical_research_questions_prompt_by_default():
    llm = _RecordingLLM("What is X?")
    service = AISummaryService(llm_fn=llm)
    await service.generate_research_questions("AI", count=3)
    expected = (
        "Generate 3 specific research questions about: AI\n"
        "Format: one question per line, starting with a question word."
    )
    assert llm.last_prompt == expected


@pytest.mark.asyncio
async def test_should_use_byte_identical_findings_summary_prompt_by_default():
    llm = _RecordingLLM("Summary text.")
    service = AISummaryService(llm_fn=llm)
    findings = [{"title": "Finding 1", "content": "Machine learning improves accuracy."}]
    await service.summarize_findings(findings, style="medium")
    from iil_researchfw.analysis.summary import _STYLE_INSTRUCTIONS

    expected_content = "- Finding 1: Machine learning improves accuracy."
    expected = (
        f"{_STYLE_INSTRUCTIONS['medium']}\n\nForschungsergebnisse (Grundlage):\n{expected_content}"
    )
    assert llm.first_prompt == expected


# --- AISummaryService: Injektion wirkt --------------------------------------


@pytest.mark.asyncio
async def test_should_use_injected_sources_analysis_prompt():
    custom = SummaryPrompts(sources_analysis="CUSTOM n={source_count} t={titles} l={max_length}")
    llm = _RecordingLLM("x")
    service = AISummaryService(llm_fn=llm, prompts=custom)
    await service.summarize_sources([{"title": "A"}, {"title": "B"}], max_length=42)
    assert llm.last_prompt == "CUSTOM n=2 t=A, B l=42"


@pytest.mark.asyncio
async def test_should_use_injected_findings_summary_prompt():
    custom = SummaryPrompts(
        findings_summary="STYLE={style_instruction}|CITE={cite_instruction}|C={content}"
    )
    llm = _RecordingLLM("x")
    service = AISummaryService(llm_fn=llm, prompts=custom)
    await service.summarize_findings(
        [{"title": "F1", "content": "c1"}], style="medium", citation_style="none"
    )
    assert llm.first_prompt.startswith("STYLE=")
    assert "|C=- F1: c1" in llm.first_prompt
