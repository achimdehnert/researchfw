"""Tests for AcademicSearchService."""
import httpx
import pytest
import respx

from iil_researchfw.search.academic import AcademicSearchService
from tests.conftest import ARXIV_XML_FIXTURE, OPENALEX_FIXTURE, SEMANTIC_SCHOLAR_FIXTURE


def _mock_sources(arxiv_status: int = 200) -> None:
    respx.get("https://export.arxiv.org/api/query").mock(
        return_value=httpx.Response(arxiv_status, text=ARXIV_XML_FIXTURE if arxiv_status == 200 else "")
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


@pytest.mark.asyncio
async def test_search_returns_papers():
    with respx.mock:
        _mock_sources()
        service = AcademicSearchService(cache_ttl_seconds=0)
        papers = await service.search("machine learning", max_results=10)
    assert len(papers) > 0
    assert all(hasattr(p, "title") for p in papers)


@pytest.mark.asyncio
async def test_partial_failure_isolated():
    """arxiv 429 must not abort the full search."""
    with respx.mock:
        _mock_sources(arxiv_status=429)
        service = AcademicSearchService(cache_ttl_seconds=0)
        papers = await service.search("test query")
    assert isinstance(papers, list)


@pytest.mark.asyncio
async def test_cache_hit():
    with respx.mock:
        _mock_sources()
        service = AcademicSearchService(cache_ttl_seconds=60)
        p1 = await service.search("cache test")
        p2 = await service.search("cache test")
    assert p1 == p2


@pytest.mark.asyncio
async def test_semantic_scholar_url_is_web_not_api():
    """Regression: S2 URLs must point to www.semanticscholar.org, not api."""
    with respx.mock:
        _mock_sources()
        service = AcademicSearchService(cache_ttl_seconds=0)
        papers = await service.search("test", sources=["semantic_scholar"])
    assert len(papers) > 0
    for p in papers:
        if p.source == "semantic_scholar":
            assert "www.semanticscholar.org" in p.url, f"Expected web URL, got: {p.url}"
            assert "api.semanticscholar.org" not in p.url


@pytest.mark.asyncio
async def test_semantic_scholar_extracts_journal():
    """S2 parser should extract journal/venue."""
    service = AcademicSearchService(cache_ttl_seconds=0)
    data = {"data": [{
        "paperId": "x1",
        "title": "Test",
        "authors": [],
        "abstract": "",
        "year": 2024,
        "externalIds": {},
        "citationCount": 0,
        "openAccessPdf": None,
        "journal": {"name": "Nature"},
        "venue": "Nature Conference",
    }]}
    papers = service._parse_semantic_scholar(data)
    assert papers[0].journal == "Nature"


@pytest.mark.asyncio
async def test_openalex_reconstructs_abstract():
    """OpenAlex parser should reconstruct abstract from inverted index."""
    with respx.mock:
        _mock_sources()
        service = AcademicSearchService(cache_ttl_seconds=0)
        papers = await service.search("test", sources=["openalex"])
    oa_papers = [p for p in papers if p.source == "openalex"]
    assert len(oa_papers) > 0
    assert oa_papers[0].abstract == "A review of transformers"


def test_reconstruct_abstract_empty():
    """_reconstruct_abstract handles None and empty dict."""
    service = AcademicSearchService()
    assert service._reconstruct_abstract(None) == ""
    assert service._reconstruct_abstract({}) == ""
