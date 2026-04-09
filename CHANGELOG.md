# Changelog

All notable changes to `iil-researchfw` are documented here.

## [Unreleased]

## [0.6.0] — 2026-04-09

### Added
- **Citation Graph Expansion** (ADR-160 Phase 5): Follow references and citations of top papers via Semantic Scholar Graph API
  - `get_references()` / `get_citations()` on AcademicSearchService
  - `_expand_via_citations()`: traverses top-5 papers, fetches refs+cites, deduplicates
  - `_get_s2_paper_id()`: resolves DOI, ArXiv ID, or S2 URL to paper identifier
  - Opt-in via `expand_citations=True`
- **Iterative Gap Analysis** (ADR-160 Phase 6): LLM identifies missing aspects and generates follow-up queries
  - `_analyze_gaps()`: LLM reviews current results, identifies gaps, generates new queries
  - `search_rounds` parameter (1-3, default 1) controls iteration depth
  - Each round: gap analysis → new queries → search → score → merge
- 15 new tests for Phase 5+6 (89 total)

## [0.5.0] — 2026-04-09

### Added
- **SmartSearchService** (ADR-160): LLM-powered search pipeline with query expansion and relevance scoring
  - `_expand_query()`: LLM generates 3-5 optimized academic search queries from a topic
  - `_score_relevance()`: LLM rates each paper 0-10 with reason (batched, chunks of 10)
  - Graceful degradation: falls back to basic keyword search if LLM unavailable
  - New exports: `SmartSearchService`, `SmartSearchResult`, `ScoredPaper`
- 13 new tests for SmartSearchService (74 total)

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
