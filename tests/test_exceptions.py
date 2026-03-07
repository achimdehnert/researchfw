"""Tests for exception hierarchy."""
from iil_researchfw.core.exceptions import (
    APIError, CitationError, ExportError, RateLimitError, ResearchError, SearchError,
)


def test_api_error_message():
    err = APIError("brave", 429, "rate limited")
    assert "brave" in str(err)
    assert "429" in str(err)
    assert err.service == "brave"
    assert err.status_code == 429


def test_rate_limit_error_is_api_error():
    err = RateLimitError("arxiv", 429)
    assert isinstance(err, APIError)
    assert isinstance(err, ResearchError)


def test_exception_hierarchy():
    for cls in [APIError, SearchError, CitationError, ExportError]:
        assert issubclass(cls, ResearchError)
