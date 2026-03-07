"""Tests for AISummaryService and make_together_llm."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iil_researchfw.analysis.summary import AISummaryService, make_together_llm

FINDINGS = [
    {"title": "Finding 1", "content": "Machine learning improves accuracy."},
    {"title": "Finding 2", "content": "Transformers outperform RNNs."},
]


@pytest.mark.asyncio
async def test_summarize_with_llm():
    mock_llm = AsyncMock(return_value="Summary from LLM.")
    service = AISummaryService(llm_fn=mock_llm)
    result = await service.summarize_findings(FINDINGS)
    assert result["ai_generated"] is True
    mock_llm.assert_called()


@pytest.mark.asyncio
async def test_summarize_fallback():
    result = await AISummaryService().summarize_findings(FINDINGS)
    assert result["ai_generated"] is False
    assert len(result["summary"]) > 0


@pytest.mark.asyncio
async def test_empty_findings():
    result = await AISummaryService().summarize_findings([])
    assert result["summary"] == ""


@pytest.mark.asyncio
async def test_questions_fallback():
    questions = await AISummaryService().generate_research_questions("ML", count=3)
    assert len(questions) == 3


@pytest.mark.asyncio
async def test_summarize_all_levels():
    for style in ("simple", "medium", "complex", "scientific"):
        mock_llm = AsyncMock(return_value=f"Summary at {style} level.")
        service = AISummaryService(llm_fn=mock_llm)
        result = await service.summarize_findings(FINDINGS, style=style)
        assert result["ai_generated"] is True
        assert style in result["style"] or result["summary"]


@pytest.mark.asyncio
async def test_summarize_sources_with_llm():
    mock_llm = AsyncMock(return_value="Thematic analysis.")
    service = AISummaryService(llm_fn=mock_llm)
    sources = [{"title": "Paper A"}, {"title": "Paper B"}]
    result = await service.summarize_sources(sources)
    assert result["ai_generated"] is True


@pytest.mark.asyncio
async def test_summarize_sources_empty():
    result = await AISummaryService().summarize_sources([])
    assert result["summary"] == ""


@pytest.mark.asyncio
async def test_extract_key_points_with_llm():
    mock_llm = AsyncMock(return_value="- Point 1\n- Point 2\n- Point 3")
    service = AISummaryService(llm_fn=mock_llm)
    points = await service.extract_key_points("Some text.", max_points=3)
    assert len(points) <= 3


@pytest.mark.asyncio
async def test_questions_with_llm():
    mock_llm = AsyncMock(return_value="What is X?\nHow does Y work?\nWhy does Z happen?")
    service = AISummaryService(llm_fn=mock_llm)
    questions = await service.generate_research_questions("AI", count=3)
    assert len(questions) <= 3


@pytest.mark.asyncio
async def test_make_together_llm_no_key():
    llm = make_together_llm(api_key="")
    result = await llm("test prompt")
    assert result == ""


@pytest.mark.asyncio
async def test_make_together_llm_with_key():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Generated summary"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        llm = make_together_llm(api_key="test-key")
        result = await llm("test prompt", max_tokens=100)
        assert result == "Generated summary"
