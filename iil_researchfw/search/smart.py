"""Smart search — LLM-powered query expansion + relevance scoring (ADR-160)."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from iil_researchfw.core.protocols import LLMCallable
from iil_researchfw.search.academic import AcademicPaper, AcademicSearchService

logger = logging.getLogger(__name__)

QUERY_EXPANSION_PROMPT = """You are an academic research assistant. Given the research topic below, generate {max_queries} precise academic search queries that would find the most relevant papers.

Research topic: "{topic}"

Include:
- Synonyms and alternative phrasings
- Key technical terms in the field
- Names of prominent researchers if well-known
- Both broad and specific queries
- English queries (even if the topic is in another language)

Return ONLY valid JSON: {{"queries": ["query1", "query2", ...]}}"""

RELEVANCE_SCORING_PROMPT = """You are an academic relevance expert. Rate each paper's relevance to the research topic on a scale of 0-10.

Research topic: "{topic}"

Papers to evaluate:
{papers_json}

Scoring guide:
- 10: Directly addresses the core research question
- 7-9: Highly relevant, covers key aspects
- 4-6: Partially relevant, tangential connection
- 1-3: Weak relevance, mostly unrelated
- 0: Completely irrelevant

Return ONLY valid JSON array: [{{"index": 0, "score": 8, "reason": "brief reason"}}, ...]"""


@dataclass
class ScoredPaper:
    """Academic paper with LLM-assigned relevance score."""

    paper: AcademicPaper
    relevance_score: float = 0.0
    relevance_reason: str = ""


@dataclass
class SmartSearchResult:
    """Result from SmartSearchService including metadata."""

    papers: list[ScoredPaper] = field(default_factory=list)
    queries_used: list[str] = field(default_factory=list)
    total_found: int = 0
    total_after_filter: int = 0
    search_duration_seconds: float = 0.0


class SmartSearchService:
    """
    LLM-powered academic search (ADR-160, Option B).

    Pipeline:
    1. LLM expands user topic into 3-5 optimized search queries
    2. AcademicSearchService searches all sources concurrently
    3. Fuzzy dedup merges results
    4. LLM scores each paper for relevance (batch of 10)
    5. Filter by relevance threshold

    Graceful degradation: if LLM is unavailable, falls back to
    basic keyword search via AcademicSearchService.
    """

    def __init__(
        self,
        llm_fn: LLMCallable,
        academic_service: AcademicSearchService | None = None,
        relevance_threshold: float = 7.0,
        max_queries: int = 4,
        scoring_batch_size: int = 10,
    ) -> None:
        self._llm_fn = llm_fn
        self._academic = academic_service or AcademicSearchService()
        self._relevance_threshold = relevance_threshold
        self._max_queries = max_queries
        self._scoring_batch_size = scoring_batch_size

    async def search(
        self,
        topic: str,
        max_results: int = 20,
        sources: list[str] | None = None,
    ) -> SmartSearchResult:
        """Run the full smart search pipeline."""
        t0 = time.monotonic()
        result = SmartSearchResult()

        # Step 1: LLM Query Expansion
        queries = await self._expand_query(topic)
        result.queries_used = queries

        if not queries:
            logger.warning("SmartSearch: query expansion failed, falling back to raw topic")
            queries = [topic]

        # Step 2: Search all queries across all sources
        all_papers: list[AcademicPaper] = []
        for query in queries:
            papers = await self._academic.search(
                query=query,
                sources=sources,
                max_results=max_results,
            )
            all_papers.extend(papers)

        # Step 3: Dedup (academic service already dedups per-query, but cross-query needs it)
        all_papers = self._academic._deduplicate(all_papers)
        result.total_found = len(all_papers)

        if not all_papers:
            result.search_duration_seconds = time.monotonic() - t0
            return result

        # Step 4: LLM Relevance Scoring (batched)
        scored = await self._score_relevance(all_papers, topic)

        # Step 5: Filter by threshold
        filtered = [s for s in scored if s.relevance_score >= self._relevance_threshold]
        filtered.sort(key=lambda s: s.relevance_score, reverse=True)
        result.papers = filtered[:max_results]
        result.total_after_filter = len(filtered)
        result.search_duration_seconds = time.monotonic() - t0

        logger.info(
            "SmartSearch: %d found → %d after scoring → %d after filter (%.1fs)",
            result.total_found,
            len(scored),
            result.total_after_filter,
            result.search_duration_seconds,
        )
        return result

    async def _expand_query(self, topic: str) -> list[str]:
        """Use LLM to generate optimized search queries from a topic."""
        prompt = QUERY_EXPANSION_PROMPT.format(topic=topic, max_queries=self._max_queries)
        try:
            response = await self._llm_fn(prompt, max_tokens=300)
            data = json.loads(self._extract_json(response))
            queries = data.get("queries", [])
            if isinstance(queries, list) and queries:
                return [str(q) for q in queries[: self._max_queries]]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("SmartSearch: query expansion parse error: %s", exc)
        except Exception as exc:
            logger.warning("SmartSearch: query expansion LLM error: %s", exc)
        return [topic]

    async def _score_relevance(
        self, papers: list[AcademicPaper], topic: str
    ) -> list[ScoredPaper]:
        """Score papers in batches using LLM."""
        all_scored: list[ScoredPaper] = []

        for i in range(0, len(papers), self._scoring_batch_size):
            batch = papers[i : i + self._scoring_batch_size]
            scored_batch = await self._score_batch(batch, topic, offset=i)
            all_scored.extend(scored_batch)

        return all_scored

    async def _score_batch(
        self, papers: list[AcademicPaper], topic: str, offset: int = 0
    ) -> list[ScoredPaper]:
        """Score a single batch of papers via LLM."""
        papers_for_prompt = [
            {
                "index": idx,
                "title": p.title,
                "abstract": (p.abstract[:300] + "…") if len(p.abstract) > 300 else p.abstract,
                "authors": ", ".join(p.authors[:3]),
                "source": p.source,
                "year": p.publication_date,
            }
            for idx, p in enumerate(papers)
        ]

        prompt = RELEVANCE_SCORING_PROMPT.format(
            topic=topic,
            papers_json=json.dumps(papers_for_prompt, ensure_ascii=False, indent=2),
        )

        try:
            response = await self._llm_fn(prompt, max_tokens=500)
            scores = json.loads(self._extract_json(response))
            if isinstance(scores, list):
                score_map = {item["index"]: item for item in scores if isinstance(item, dict)}
                return [
                    ScoredPaper(
                        paper=p,
                        relevance_score=float(score_map.get(idx, {}).get("score", 0)),
                        relevance_reason=str(score_map.get(idx, {}).get("reason", "")),
                    )
                    for idx, p in enumerate(papers)
                ]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("SmartSearch: relevance scoring parse error (batch %d): %s", offset, exc)
        except Exception as exc:
            logger.warning("SmartSearch: relevance scoring LLM error (batch %d): %s", offset, exc)

        # Fallback: return all papers with score 5 (neutral) so they aren't lost
        return [ScoredPaper(paper=p, relevance_score=5.0, relevance_reason="LLM scoring failed") for p in papers]

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from LLM response that may contain markdown fences or preamble."""
        text = text.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1]
            text = text.split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1]
            text = text.split("```", 1)[0]
        # Find first { or [
        for i, ch in enumerate(text):
            if ch in "{[":
                # Find matching close
                depth = 0
                open_ch = ch
                close_ch = "}" if ch == "{" else "]"
                for j in range(i, len(text)):
                    if text[j] == open_ch:
                        depth += 1
                    elif text[j] == close_ch:
                        depth -= 1
                        if depth == 0:
                            return text[i : j + 1]
        return text
