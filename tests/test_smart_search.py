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


# --- Fixtures for citation graph ---

S2_CITATION_FIXTURE = {
    "data": [
        {
            "citedPaper": {
                "paperId": "abc123",
                "title": "Seminal Work on Neural Networks",
                "authors": [{"name": "Y. LeCun"}],
                "abstract": "Foundational paper on backpropagation.",
                "year": 1998,
                "externalIds": {"DOI": "10.1234/seminal"},
                "citationCount": 50000,
                "venue": "Nature",
            }
        },
        {
            "citedPaper": {
                "paperId": "def456",
                "title": "Attention Is All You Need",
                "authors": [{"name": "A. Vaswani"}],
                "abstract": "Transformer architecture.",
                "year": 2017,
                "externalIds": {"DOI": "10.1234/transformer"},
                "citationCount": 80000,
                "venue": "NeurIPS",
            }
        },
    ]
}

S2_CITING_FIXTURE = {
    "data": [
        {
            "citingPaper": {
                "paperId": "ghi789",
                "title": "Recent Advances in LLMs",
                "authors": [{"name": "J. Wei"}],
                "abstract": "Survey of large language models.",
                "year": 2024,
                "externalIds": {},
                "citationCount": 200,
                "venue": "ACL",
            }
        },
    ]
}


def _mock_citation_graph() -> None:
    """Mock Semantic Scholar citation graph endpoints."""
    respx.get(url__regex=r".*/graph/v1/paper/.*/references").mock(
        return_value=httpx.Response(200, json=S2_CITATION_FIXTURE)
    )
    respx.get(url__regex=r".*/graph/v1/paper/.*/citations").mock(
        return_value=httpx.Response(200, json=S2_CITING_FIXTURE)
    )


# --- Mock LLM functions ---

async def _mock_llm_good(prompt: str, max_tokens: int = 500, **_) -> str:
    """Mock LLM that returns valid responses for all prompt types."""
    lower = prompt.lower()
    # Gap analysis check MUST come before "search queries" since gap prompt also contains that phrase
    if "missing" in lower and "gaps" in lower:
        return json.dumps({
            "gaps": ["ethical implications of AI", "energy efficiency of training"],
            "queries": [
                "AI ethics machine learning fairness",
                "energy efficient deep learning training",
            ]
        })
    if "search queries" in lower:
        return json.dumps({
            "queries": [
                "machine learning advances 2024",
                "deep learning neural networks survey",
                "transformer architecture applications",
            ]
        })
    if "relevance" in lower:
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


# --- Phase 1-4 Tests ---

@pytest.mark.asyncio
async def test_smart_search_full_pipeline():
    """Full pipeline: expansion -> search -> scoring -> filter."""
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

    assert all(p.relevance_score >= 7.0 for p in result.papers)


@pytest.mark.asyncio
async def test_smart_search_graceful_degradation_bad_llm():
    """Bad LLM output -> falls back to raw topic search, neutral scores."""
    with respx.mock:
        _mock_sources()
        service = SmartSearchService(
            llm_fn=_mock_llm_bad,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
            relevance_threshold=0.0,
        )
        result = await service.search("test topic")

    assert result.total_found > 0
    assert "test topic" in result.queries_used


@pytest.mark.asyncio
async def test_smart_search_graceful_degradation_llm_error():
    """LLM raises exception -> falls back gracefully."""
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


# --- Phase 5: Citation Graph Expansion ---

@pytest.mark.asyncio
async def test_citation_graph_expansion():
    """expand_citations=True fetches references + citations and scores them."""
    with respx.mock:
        _mock_sources()
        _mock_citation_graph()
        service = SmartSearchService(
            llm_fn=_mock_llm_good,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
            relevance_threshold=5.0,
            expand_citations=True,
        )
        result = await service.search("machine learning")

    assert result.total_found > 0
    assert result.search_duration_seconds > 0


@pytest.mark.asyncio
async def test_citation_graph_disabled_by_default():
    """expand_citations=False (default) does NOT fetch citation graph."""
    with respx.mock:
        _mock_sources()
        service = SmartSearchService(
            llm_fn=_mock_llm_good,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
            relevance_threshold=5.0,
            expand_citations=False,
        )
        result = await service.search("machine learning")

    assert result.total_found > 0


@pytest.mark.asyncio
async def test_expand_via_citations_uses_doi():
    """_expand_via_citations builds S2 paper ID from DOI."""
    with respx.mock:
        _mock_citation_graph()
        service = SmartSearchService(
            llm_fn=_mock_llm_good,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
        )
        papers = [ScoredPaper(
            paper=AcademicPaper(title="Test", doi="10.1234/test", source="s2"),
            relevance_score=9.0,
        )]
        citation_papers = await service._expand_via_citations(papers)

    assert len(citation_papers) >= 1
    titles = [p.title for p in citation_papers]
    assert "Seminal Work on Neural Networks" in titles


@pytest.mark.asyncio
async def test_expand_via_citations_graceful_on_error():
    """Citation graph errors don't crash the pipeline."""
    with respx.mock:
        respx.get(url__regex=r".*/graph/v1/paper/.*/references").mock(
            return_value=httpx.Response(500)
        )
        respx.get(url__regex=r".*/graph/v1/paper/.*/citations").mock(
            return_value=httpx.Response(500)
        )
        service = SmartSearchService(
            llm_fn=_mock_llm_good,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
        )
        papers = [ScoredPaper(
            paper=AcademicPaper(title="Test", doi="10.1234/test", source="s2"),
            relevance_score=9.0,
        )]
        citation_papers = await service._expand_via_citations(papers)

    assert citation_papers == []


def test_get_s2_paper_id_doi():
    """_get_s2_paper_id prefers DOI."""
    p = AcademicPaper(title="T", doi="10.1234/x", arxiv_id="2401.00001")
    assert SmartSearchService._get_s2_paper_id(p) == "DOI:10.1234/x"


def test_get_s2_paper_id_arxiv():
    """_get_s2_paper_id falls back to ArXiv."""
    p = AcademicPaper(title="T", arxiv_id="2401.00001")
    assert SmartSearchService._get_s2_paper_id(p) == "ArXiv:2401.00001"


def test_get_s2_paper_id_url():
    """_get_s2_paper_id falls back to S2 URL."""
    p = AcademicPaper(title="T", url="https://www.semanticscholar.org/paper/abc123")
    assert SmartSearchService._get_s2_paper_id(p) == "abc123"


def test_get_s2_paper_id_none():
    """_get_s2_paper_id returns None when no ID available."""
    p = AcademicPaper(title="T", url="https://arxiv.org/abs/2401.00001")
    assert SmartSearchService._get_s2_paper_id(p) is None


# --- Phase 6: Iterative Gap Analysis ---

@pytest.mark.asyncio
async def test_iterative_search_two_rounds():
    """search_rounds=2 performs gap analysis and additional search."""
    with respx.mock:
        _mock_sources()
        service = SmartSearchService(
            llm_fn=_mock_llm_good,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
            relevance_threshold=5.0,
            search_rounds=2,
        )
        result = await service.search("machine learning")

    assert len(result.queries_used) > 3
    assert result.total_found > 0


@pytest.mark.asyncio
async def test_iterative_search_default_one_round():
    """search_rounds=1 (default) does NOT do gap analysis."""
    with respx.mock:
        _mock_sources()
        service = SmartSearchService(
            llm_fn=_mock_llm_good,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
            relevance_threshold=5.0,
            search_rounds=1,
        )
        result = await service.search("machine learning")

    assert len(result.queries_used) == 3


@pytest.mark.asyncio
async def test_gap_analysis_parses_json():
    """_analyze_gaps returns new queries from LLM response."""
    service = SmartSearchService(llm_fn=_mock_llm_good)
    papers = [ScoredPaper(
        paper=AcademicPaper(title="Deep Learning Survey"),
        relevance_score=9.0,
    )]
    gaps = await service._analyze_gaps(papers, "machine learning")
    assert len(gaps) == 2
    assert "AI ethics machine learning fairness" in gaps


@pytest.mark.asyncio
async def test_gap_analysis_fallback_on_error():
    """_analyze_gaps returns [] on LLM failure."""
    service = SmartSearchService(llm_fn=_mock_llm_error)
    papers = [ScoredPaper(paper=AcademicPaper(title="Test"), relevance_score=8.0)]
    gaps = await service._analyze_gaps(papers, "topic")
    assert gaps == []


@pytest.mark.asyncio
async def test_gap_analysis_empty_papers():
    """_analyze_gaps returns [] for empty paper list."""
    service = SmartSearchService(llm_fn=_mock_llm_good)
    gaps = await service._analyze_gaps([], "topic")
    assert gaps == []


@pytest.mark.asyncio
async def test_search_rounds_clamped():
    """search_rounds is clamped between 1 and 3."""
    s1 = SmartSearchService(llm_fn=_mock_llm_good, search_rounds=0)
    assert s1._search_rounds == 1
    s2 = SmartSearchService(llm_fn=_mock_llm_good, search_rounds=10)
    assert s2._search_rounds == 3


# --- Phase 5+6 combined ---

@pytest.mark.asyncio
async def test_full_pipeline_all_features():
    """Full pipeline with citations + iterative search."""
    with respx.mock:
        _mock_sources()
        _mock_citation_graph()
        service = SmartSearchService(
            llm_fn=_mock_llm_good,
            academic_service=AcademicSearchService(cache_ttl_seconds=0),
            relevance_threshold=5.0,
            expand_citations=True,
            search_rounds=2,
        )
        result = await service.search("machine learning")

    assert result.total_found > 0
    assert len(result.queries_used) > 3
    assert result.search_duration_seconds > 0
