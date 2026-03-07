"""Exception hierarchy for iil-researchfw."""


class ResearchError(Exception):
    """Base exception for iil-researchfw."""


class APIError(ResearchError):
    """External API call failed."""

    def __init__(self, service: str, status_code: int, message: str = "") -> None:
        self.service = service
        self.status_code = status_code
        super().__init__(f"{service} API error {status_code}: {message}")


class RateLimitError(APIError):
    """Rate limit exceeded (HTTP 429)."""


class SearchError(ResearchError):
    """Search operation failed."""


class CitationError(ResearchError):
    """Citation resolution failed."""


class ExportError(ResearchError):
    """Export operation failed."""
