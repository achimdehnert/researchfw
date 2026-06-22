"""iil-researchfw — Platform research framework.

Async, source-agnostic research over the web and academic corpora: multi-source
search (Brave + academic), relevance scoring, AI summarisation, citation
formatting, and document export.

Public API is organised by submodule — import from these directly:

- ``iil_researchfw.core``       — ``ResearchService``, models (``ResearchContext``,
  ``ResearchOutput``, ``Finding``, ``Source``), protocols, exceptions
- ``iil_researchfw.search``     — ``BraveSearchService``, ``AcademicSearchService``,
  ``SmartSearchService`` (scored multi-source search)
- ``iil_researchfw.analysis``   — ``AISummaryService`` summarisation + relevance scoring
- ``iil_researchfw.citations``  — ``CitationService``, ``CitationStyle``, ``Citation``
- ``iil_researchfw.export``     — ``ResearchExportService`` (docx/markdown export)
- ``iil_researchfw._internal``  — private cache + rate-limiter helpers (not public API)

``__version__`` is resolved from the installed package metadata.
"""

from importlib.metadata import PackageNotFoundError, version

from iil_researchfw.analysis.summary import AISummaryService, make_together_llm
from iil_researchfw.citations.formatter import (
    Author,
    Citation,
    CitationService,
    CitationStyle,
    SourceType,
)
from iil_researchfw.core.models import Finding, ResearchContext, ResearchOutput, Source
from iil_researchfw.core.service import ResearchService
from iil_researchfw.export.service import ResearchExportService
from iil_researchfw.search.academic import AcademicSearchService
from iil_researchfw.search.brave import BraveSearchService
from iil_researchfw.search.smart import ScoredPaper, SmartSearchResult, SmartSearchService

try:
    __version__ = version("iil-researchfw")
except PackageNotFoundError:  # source checkout without an install
    __version__ = "0.0.0.dev0"

__all__ = [
    "__version__",
    "ResearchService",
    "ResearchContext",
    "ResearchOutput",
    "Finding",
    "Source",
    "AcademicSearchService",
    "BraveSearchService",
    "Citation",
    "CitationService",
    "CitationStyle",
    "Author",
    "SourceType",
    "AISummaryService",
    "make_together_llm",
    "ResearchExportService",
    "SmartSearchService",
    "SmartSearchResult",
    "ScoredPaper",
]
