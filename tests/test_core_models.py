"""Tests for core Pydantic models."""
from datetime import datetime
import pytest
from iil_researchfw.core.models import Finding, ResearchContext, ResearchOutput, Source


def test_finding_creation():
    f = Finding(id="1", title="Test", content="Content")
    assert f.id == "1"
    assert f.relevance_score == 0.0
    assert isinstance(f.created_at, datetime)


def test_finding_is_frozen():
    f = Finding(id="1", title="Test", content="Content")
    with pytest.raises(Exception):
        f.id = "2"  # type: ignore[misc]


def test_finding_relevance_bounds():
    with pytest.raises(Exception):
        Finding(id="1", title="T", content="C", relevance_score=1.5)


def test_source_creation():
    s = Source(url="https://example.com", title="Example")
    assert s.domain == ""
    assert isinstance(s.fetched_at, datetime)


def test_research_context_defaults():
    ctx = ResearchContext(query="test query")
    assert ctx.max_sources == 10
    assert ctx.language == "de"
    assert ctx.include_local is False


def test_research_output_to_dict():
    out = ResearchOutput(success=True, query="test")
    d = out.to_dict()
    assert d["success"] is True
    assert d["sources"] == []
