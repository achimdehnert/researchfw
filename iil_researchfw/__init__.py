"""iil-researchfw — Platform research framework."""

__version__ = "0.1.0"

from iil_researchfw.analysis.summary import AISummaryService
from iil_researchfw.citations.formatter import CitationService, CitationStyle
from iil_researchfw.core.models import Finding, ResearchContext, ResearchOutput, Source
from iil_researchfw.core.service import ResearchService
from iil_researchfw.export.service import ResearchExportService
from iil_researchfw.search.academic import AcademicSearchService
from iil_researchfw.search.brave import BraveSearchService

__all__ = [
    "ResearchService",
    "ResearchContext",
    "ResearchOutput",
    "Finding",
    "Source",
    "AcademicSearchService",
    "BraveSearchService",
    "CitationService",
    "CitationStyle",
    "AISummaryService",
    "ResearchExportService",
]
