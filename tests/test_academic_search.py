"""Tests for AcademicSearchService."""
import httpx
import pytest
import respx

from iil_researchfw.search.academic import AcademicPaper, AcademicSearchService
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


def test_fuzzy_dedup_exact_match():
    """Exact same title is deduped."""
    service = AcademicSearchService()
    papers = [
        AcademicPaper(title="Deep Learning", source="arxiv"),
        AcademicPaper(title="Deep Learning", source="openalex"),
    ]
    result = service._deduplicate(papers)
    assert len(result) == 1


def test_fuzzy_dedup_subtitle_variation():
    """Same paper with/without subtitle is deduped."""
    service = AcademicSearchService()
    papers = [
        AcademicPaper(title="Deep Learning: A Comprehensive Survey", source="arxiv"),
        AcademicPaper(title="Deep Learning A Comprehensive Survey", source="openalex"),
    ]
    result = service._deduplicate(papers)
    assert len(result) == 1


def test_fuzzy_dedup_punctuation_difference():
    """Titles differing only in punctuation are deduped."""
    service = AcademicSearchService()
    papers = [
        AcademicPaper(title="Attention Is All You Need.", source="arxiv"),
        AcademicPaper(title="Attention Is All You Need", source="s2"),
    ]
    result = service._deduplicate(papers)
    assert len(result) == 1


def test_fuzzy_dedup_keeps_different_papers():
    """Genuinely different papers are kept."""
    service = AcademicSearchService()
    papers = [
        AcademicPaper(title="Deep Learning for Computer Vision", source="arxiv"),
        AcademicPaper(title="Reinforcement Learning in Robotics", source="openalex"),
    ]
    result = service._deduplicate(papers)
    assert len(result) == 2


def test_fuzzy_dedup_doi_takes_priority():
    """Same DOI dedupes even if titles are different."""
    service = AcademicSearchService()
    papers = [
        AcademicPaper(title="Paper A (preprint)", doi="10.1234/test", source="arxiv"),
        AcademicPaper(title="Paper A: Final Version", doi="10.1234/test", source="s2"),
    ]
    result = service._deduplicate(papers)
    assert len(result) == 1


def test_normalize_title():
    service = AcademicSearchService()
    assert service._normalize_title("  Hello, World!  ") == "hello world"
    assert service._normalize_title("A—B: C") == "ab c"


def test_titles_similar_threshold():
    service = AcademicSearchService()
    assert service._titles_similar("deep learning survey", "deep learning survey") is True
    assert service._titles_similar("deep learning survey methods", "deep learning survey") is True
    assert service._titles_similar("cats", "dogs") is False
