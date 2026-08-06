# Changelog

All notable changes to `iil-researchfw` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.6.1] — 2026-08-06

### Fixed
- **Der Wiederholungsversuch greift jetzt auch bei 429** (#16). Die `@retry`-Decorator
  in `academic.py` fingen ausschließlich `httpx.HTTPStatusError`; die Registerfunktionen
  werfen bei 429 aber `RateLimitError` — und zwar **vor** `raise_for_status()`.
  `RateLimitError` stammt von `ResearchError`, nicht von httpx, also feuerte der
  Mechanismus ausgerechnet für den Fall nicht, für den er dem Namen nach da ist.
  Ein einziger 429 beendete das Register für den gesamten Lauf.

  Belegt durch einen A/B-Vergleich bei gleichem Code und gleichen vier Suchbegriffen
  (achimdehnert/writing-hub#517): bei `403` (→ `HTTPStatusError`) liefen 12 Anfragen,
  also drei Versuche je Begriff; bei `429` nur 4, also einer. Der Backoff selbst
  funktionierte einwandfrei — er war nur für eine Fehlerart blind.

  Betroffen waren **vier** Registerfunktionen, nicht nur die auffällige: `_search_arxiv`
  wirft denselben Fehler, dort fällt es nur nicht auf, weil arXiv selten drosselt. Die
  gemeinsame Konstante `WIEDERHOLBAR` hält beide Fehlerarten an einer Stelle.

  In Produktion nachgemessen (writing-hub): ohne Wiederholung **1 von 4** Anfragen
  erfolgreich, mit Wiederholung **4 von 4**.
- 7 neue Tests, davon zwei Gegenproben: der alte Filter wiederholt einen 429
  nachweislich **nicht**, und ein AST-Test prüft **alle** Registerfunktionen statt nur
  der einen, die aufgefallen ist. (96 gesamt)

---

## [0.6.0] — 2026-04-09

### Added
- **Citation Graph Expansion** (ADR-160 Phase 5): Follow references and citations of top papers via Semantic Scholar Graph API
  - `get_references()` / `get_citations()` on `AcademicSearchService`
  - `_expand_via_citations()`: traverses top-5 papers, fetches refs+cites, deduplicates
  - `_get_s2_paper_id()`: resolves DOI, ArXiv ID, or S2 URL to paper identifier
  - Opt-in via `expand_citations=True`
- **Iterative Gap Analysis** (ADR-160 Phase 6): LLM identifies missing aspects and generates follow-up queries
  - `_analyze_gaps()`: LLM reviews current results, identifies gaps, generates new queries
  - `search_rounds` parameter (1-3, default 1) controls iteration depth
  - Each round: gap analysis → new queries → search → score → merge
- 15 new tests for Phase 5+6 (89 total)

---

## [0.5.0] — 2026-04-09

### Added
- **SmartSearchService** (ADR-160): LLM-powered search pipeline with query expansion and relevance scoring
  - `_expand_query()`: LLM generates 3-5 optimized academic search queries from a topic
  - `_score_relevance()`: LLM rates each paper 0-10 with reason (batched, chunks of 10)
  - Graceful degradation: falls back to basic keyword search if LLM unavailable
  - New exports: `SmartSearchService`, `SmartSearchResult`, `ScoredPaper`
- 13 new tests for SmartSearchService (74 total)

---

## [0.4.1] — 2026-04-09

### Improved
- **Fuzzy title dedup**: Papers with slightly different titles deduplicated using token overlap ratio (≥85% threshold)
- **TTLCache max_size + LRU eviction**: Cache enforces configurable `max_size` (default 256) with LRU eviction

### Added
- 12 new tests: 7 fuzzy dedup + 5 cache LRU (61 total)

---

## [0.4.0] — 2026-04-09

### Fixed
- **Semantic Scholar URL bug**: Paper URLs now point to `www.semanticscholar.org`
- **`make_together_llm`**: `httpx.AsyncClient` created once per call instead of per retry
- **User-Agent headers**: Dynamic `__version__` instead of hardcoded version strings

### Added
- Semantic Scholar journal/venue field support
- OpenAlex abstract reconstruction from `abstract_inverted_index`
- Optional `semantic_scholar_api_key` for higher rate limits
- 5 new regression tests (49 total)

---

> **Note:** Versions 0.2.0–0.3.x were released but not individually documented here.
> See git log for details.

---

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
