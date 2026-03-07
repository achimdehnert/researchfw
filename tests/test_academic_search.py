"""Tests for AcademicSearchService."""
import pytest
import respx
import httpx
from iil_researchfw.search.academic import AcademicSearchService
from tests.conftest import ARXIV_XML_FIXTURE, SEMANTIC_SCHOLAR_FIXTURE, OPENALEX_FIXTURE


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
