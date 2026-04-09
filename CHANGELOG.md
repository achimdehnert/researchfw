# Changelog

All notable changes to `iil-researchfw` are documented here.

## [Unreleased]

## [0.4.1] — 2026-04-09

### Improved
- **Fuzzy title dedup**: Papers with slightly different titles (punctuation, subtitles, reordering) are now correctly deduplicated using token overlap ratio (≥85% threshold)
- **TTLCache max_size + LRU eviction**: Cache now enforces a configurable `max_size` (default 256) with LRU eviction. Expired entries are proactively cleaned on `set()`. New `size` property and `_evict_expired()` method.

### Added
- 12 new tests: 7 fuzzy dedup + 5 cache LRU (61 total)

## [0.4.0] — 2026-04-09

### Fixed
- **Semantic Scholar URL bug**: Paper URLs now point to `www.semanticscholar.org` instead of `api.semanticscholar.org` — links are now clickable for users
- **make_together_llm**: httpx.AsyncClient now created once per call instead of per retry attempt — fewer connections, faster retries
- **User-Agent headers**: `CitationService.from_doi()` and `from_isbn()` now use dynamic `__version__` instead of hardcoded version strings

### Added
- **Semantic Scholar journal/venue**: API now queries `venue` and `journal` fields — papers include journal name
- **OpenAlex abstract reconstruction**: Abstracts reconstructed from `abstract_inverted_index` — previously missing for all OpenAlex papers
- **Semantic Scholar API key support**: Optional `semantic_scholar_api_key` parameter on `AcademicSearchService` for higher rate limits
- 5 new regression tests (49 total)

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
