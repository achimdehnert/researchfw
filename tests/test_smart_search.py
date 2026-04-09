"""Tests for SmartSearchService (ADR-160)."""
import json

import httpx
import pytest
import respx

from iil_researchfw.search.academic import AcademicPaper, AcademicSearchService
from iil_researchfw.search.smart import ScoredPaper, SmartSearchResult, SmartSearchService
from tests.conftest import ARXIV_XML_FIXTURE, OPENALEX_FIXTURE, SEMANTIC_SCHOLAR_FIXTURE


def _mock_sources() -> None:
    respx.get("https://export.arxiv.org/api/query").mock(
        return_value=httpx.Response(200, text=ARXIV_XML_FIXTURE)
    )
    respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
        return_value=httpx.Response(200, json=SEMANTIC_SCHOLAR_FIXTURE)
    )
    respx.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=OPENALEX_FIXTURE)
    )
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": []}})
    )


# --- Mock LLM functions ---

async def _mock_llm_good(prompt: str, max_tokens: int = 500, **_) -> str:
    """Mock LLM that returns valid query expansion and relevance scores."""
    if "search queries" in prompt.lower():
        return json.dumps({
            "queries": [
                "machine learning advances 2024",
                "deep learning neural networks survey",
                "transformer architecture applications",
            ]
        })
    if "relevance" in prompt.lower():
        return json.dumps([
            {"index": 0, "score": 9, "reason": "Directly about deep learning"},
            {"index": 1, "score": 8, "reason": "Related transformer work"},
            {"index": 2, "score": 3, "reason": "Only tangentially related"},
        ])
    return ""


async def _mock_llm_bad(prompt: str, max_tokens: int = 500, **_) -> str:
    """Mock LLM that returns garbage."""
    return "I don't understand the question, here's a poem instead."


async def _mock_llm_error(prompt: str, max_tokens: int = 500, **_) -> str:
    """Mock LLM that raises an exception."""
    raise ConnectionError("LLM service unavailable")


# --- Tests ---

@pytest.mark.asyncio
async def test_smart_search_full_pipeline():
    """Full pipeline: expansion → search → scoring → filter."""
    with respx.mock:
        _mock_sources()
        service = SmartSearchService(
            llm_fn=_mock_llm_good,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
            relevance_threshold=5.0,
        )
        result = await service.search("machine learning")

    assert isinstance(result, SmartSearchResult)
    assert len(result.queries_used) == 3
    assert result.total_found > 0
    assert result.search_duration_seconds > 0
    # Papers with score >= 5 should be kept
    assert all(p.relevance_score >= 5.0 for p in result.papers)


@pytest.mark.asyncio
async def test_smart_search_filters_low_relevance():
    """Papers below threshold should be filtered out."""
    with respx.mock:
        _mock_sources()
        service = SmartSearchService(
            llm_fn=_mock_llm_good,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
            relevance_threshold=7.0,
        )
        result = await service.search("machine learning")

    # Score 3 papers should be filtered out
    assert all(p.relevance_score >= 7.0 for p in result.papers)


@pytest.mark.asyncio
async def test_smart_search_graceful_degradation_bad_llm():
    """Bad LLM output → falls back to raw topic search, neutral scores."""
    with respx.mock:
        _mock_sources()
        service = SmartSearchService(
            llm_fn=_mock_llm_bad,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
            relevance_threshold=0.0,
        )
        result = await service.search("test topic")

    # Should still return papers (fallback to raw query)
    assert result.total_found > 0
    # Queries should contain the raw topic as fallback
    assert "test topic" in result.queries_used


@pytest.mark.asyncio
async def test_smart_search_graceful_degradation_llm_error():
    """LLM raises exception → falls back gracefully."""
    with respx.mock:
        _mock_sources()
        service = SmartSearchService(
            llm_fn=_mock_llm_error,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
            relevance_threshold=0.0,
        )
        result = await service.search("test topic")

    assert result.total_found > 0
    assert "test topic" in result.queries_used


@pytest.mark.asyncio
async def test_query_expansion_parses_json():
    """_expand_query returns list of queries from LLM JSON."""
    service = SmartSearchService(llm_fn=_mock_llm_good)
    queries = await service._expand_query("climate change agriculture")
    assert len(queries) == 3
    assert "machine learning advances 2024" in queries


@pytest.mark.asyncio
async def test_query_expansion_fallback_on_error():
    """_expand_query returns [topic] on LLM failure."""
    service = SmartSearchService(llm_fn=_mock_llm_error)
    queries = await service._expand_query("test topic")
    assert queries == ["test topic"]


@pytest.mark.asyncio
async def test_score_batch_parses_scores():
    """_score_batch correctly assigns scores from LLM output."""
    service = SmartSearchService(llm_fn=_mock_llm_good)
    papers = [
        AcademicPaper(title="Deep Learning", source="arxiv"),
        AcademicPaper(title="Transformers", source="s2"),
        AcademicPaper(title="Cooking Recipes", source="openalex"),
    ]
    scored = await service._score_batch(papers, "machine learning")
    assert len(scored) == 3
    assert scored[0].relevance_score == 9
    assert scored[1].relevance_score == 8
    assert scored[2].relevance_score == 3


@pytest.mark.asyncio
async def test_score_batch_fallback_on_error():
    """_score_batch returns neutral score 5 on LLM failure."""
    service = SmartSearchService(llm_fn=_mock_llm_error)
    papers = [AcademicPaper(title="Test", source="arxiv")]
    scored = await service._score_batch(papers, "topic")
    assert len(scored) == 1
    assert scored[0].relevance_score == 5.0
    assert "failed" in scored[0].relevance_reason


def test_extract_json_from_fenced():
    """_extract_json handles markdown-fenced JSON."""
    raw = '```json\n{"queries": ["a", "b"]}\n```'
    assert json.loads(SmartSearchService._extract_json(raw)) == {"queries": ["a", "b"]}


def test_extract_json_from_plain():
    """_extract_json handles plain JSON."""
    raw = '{"queries": ["a"]}'
    assert json.loads(SmartSearchService._extract_json(raw)) == {"queries": ["a"]}


def test_extract_json_from_preamble():
    """_extract_json handles LLM preamble before JSON."""
    raw = 'Here are the queries:\n[{"index": 0, "score": 8}]'
    assert json.loads(SmartSearchService._extract_json(raw)) == [{"index": 0, "score": 8}]


def test_smart_search_result_defaults():
    """SmartSearchResult has sensible defaults."""
    r = SmartSearchResult()
    assert r.papers == []
    assert r.queries_used == []
    assert r.total_found == 0
    assert r.search_duration_seconds == 0.0


def test_scored_paper_defaults():
    """ScoredPaper has sensible defaults."""
    p = ScoredPaper(paper=AcademicPaper(title="Test"))
    assert p.relevance_score == 0.0
    assert p.relevance_reason == ""
