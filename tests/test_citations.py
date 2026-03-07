"""Tests for CitationService and Citation formatting."""
import httpx
import pytest
import respx

from iil_researchfw.citations.formatter import (
    Author,
    Citation,
    CitationService,
    CitationStyle,
    SourceType,
)
from tests.conftest import CROSSREF_FIXTURE


def test_author_apa():
    assert Author(family="Smith", given="John").format_apa() == "Smith, J."


def test_author_ieee():
    assert Author(family="Smith", given="John").format_ieee() == "J. Smith"


def test_citation_apa_journal():
    c = Citation(
        title="Test Article", authors=[Author(family="Smith", given="John")],
        year=2024, source_type=SourceType.JOURNAL, journal="Journal of Testing",
        volume="5", issue="2", pages="100-110", doi="10.1234/test",
    )
    result = c.format(CitationStyle.APA)
    assert "Smith" in result and "2024" in result and "Journal of Testing" in result


def test_citation_in_text_two_authors():
    c = Citation(
        title="Test",
        authors=[Author(family="Smith", given="J"), Author(family="Doe", given="J")],
        year=2024,
    )
    assert c.format_in_text() == "(Smith & Doe, 2024)"


def test_citation_to_bibtex():
    c = Citation(
        title="Test", authors=[Author(family="Smith", given="J")],
        year=2024, journal="J", doi="10.1234/test",
    )
    bibtex = c.to_bibtex()
    assert "@article" in bibtex and "10.1234/test" in bibtex


def test_citation_to_ris():
    c = Citation(title="Test", authors=[Author(family="Smith", given="J")], year=2024)
    assert "TY  - JOUR" in c.to_ris()


@pytest.mark.asyncio
async def test_from_doi_resolves():
    with respx.mock:
        respx.get("https://api.crossref.org/works/10.1234/test").mock(
            return_value=httpx.Response(200, json=CROSSREF_FIXTURE)
        )
        citation = await CitationService().from_doi("10.1234/test")
    assert citation is not None
    assert citation.title == "Test Article Title"
    assert len(citation.authors) == 2
    assert citation.year == 2024


@pytest.mark.asyncio
async def test_from_doi_returns_none_on_404():
    with respx.mock:
        respx.get("https://api.crossref.org/works/invalid").mock(
            return_value=httpx.Response(404)
        )
        result = await CitationService().from_doi("invalid")
    assert result is None
