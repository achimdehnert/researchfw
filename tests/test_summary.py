"""Tests for AISummaryService."""
import pytest
from unittest.mock import AsyncMock
from iil_researchfw.analysis.summary import AISummaryService

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
