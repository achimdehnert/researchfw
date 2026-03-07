# Changelog

All notable changes to `iil-researchfw` are documented here.

## [Unreleased]

## [0.1.0] — 2026-03-07

### Added
- `core/models.py` — Pydantic v2: `Finding`, `Source`, `ResearchContext`, `ResearchOutput`
- `core/protocols.py` — `LLMCallable`, `AsyncLLMStreamCallable`, `ResearchProjectProtocol`
- `core/exceptions.py` — `ResearchError`, `APIError`, `RateLimitError`, `SearchError`, `CitationError`, `ExportError`
- `core/service.py` — `ResearchService` async orchestrator
- `search/academic.py` — `AcademicSearchService` async + concurrent (arXiv, Semantic Scholar, PubMed, OpenAlex)
- `search/brave.py` — `BraveSearchService` async
- `citations/formatter.py` — `CitationService`, `CitationStyle`, `Citation`, `Author`
- `analysis/summary.py` — `AISummaryService` LLM-agnostic
- `analysis/relevance.py` — `RelevanceScorer`
- `export/service.py` — `ResearchExportService`
- `_internal/cache.py` — `TTLCache[T]`
- `_internal/rate_limiter.py` — `RateLimiter`
