from iil_researchfw.search.academic import AcademicPaper, AcademicSearchService
from iil_researchfw.search.base import AsyncBaseSearchProvider
from iil_researchfw.search.brave import BraveSearchService, SearchResult
from iil_researchfw.search.smart import (
    ScoredPaper,
    SmartSearchPrompts,
    SmartSearchResult,
    SmartSearchService,
)

__all__ = [
    "AcademicPaper",
    "AcademicSearchService",
    "BraveSearchService",
    "SearchResult",
    "AsyncBaseSearchProvider",
    "ScoredPaper",
    "SmartSearchPrompts",
    "SmartSearchResult",
    "SmartSearchService",
]
