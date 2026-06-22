# CLAUDE.md — iil-researchfw

Operating guide for an AI agent working in this repo. Repo-specific; the
user-level `~/.claude/CLAUDE.md` still applies and wins on conflicts.

## What this is

`iil-researchfw` is the platform's **research framework**: an async,
source-agnostic toolkit for literature and web research. It runs multi-source
search (Brave web + academic providers: arXiv, Semantic Scholar, PubMed,
OpenAlex), scores and merges results, optionally summarises them with an
LLM-agnostic provider, formats citations (APA/MLA/Chicago/Harvard/IEEE/Vancouver
+ BibTeX/RIS), and exports findings (Markdown/LaTeX/DOCX). Shipped as a PyPI
library (`iil-researchfw`, import `iil_researchfw`).

## Setup

```bash
python3 -m pip install -e ".[dev]"   # editable install with dev extras
```

`__version__` is read from installed package metadata (`iil_researchfw.__version__`).

## Test / lint / types

```bash
make test     # python3 -m pytest --tb=short -q
make lint     # ruff check .
make types    # python3 -m mypy iil_researchfw   (advisory — not yet green, see Known issues)
```

- Tests use `pytest-asyncio` (`asyncio_mode = "auto"`); HTTP is stubbed with
  `respx`. Network is never hit in the suite.
- Coverage gate: `fail_under = 65` (current suite ≈ 69%).
- CI (`.github/workflows/ci.yml`) runs `ruff check`, `mypy iil_researchfw`, and
  `coverage run -m pytest` on Python 3.12 only (`requires-python >=3.12`).

## Architecture (module map)

| Module | Responsibility |
|---|---|
| `core/` | `ResearchService` orchestrator, domain models (`ResearchContext`, `ResearchOutput`, `Finding`, `Source`), protocols, exceptions |
| `search/` | `BraveSearchService` (web), `AcademicSearchService` (arXiv/S2/PubMed/OpenAlex), `SmartSearchService` (scored multi-source + citation-graph expansion + gap analysis), `base.py` shared search plumbing |
| `analysis/` | `AISummaryService` (LLM-agnostic summary/key-points/questions), `relevance.py` scoring |
| `citations/` | `CitationService`, `CitationStyle`, `Citation`, `Author`, `SourceType` formatter |
| `export/` | `ResearchExportService` — Markdown/LaTeX/DOCX export |
| `_internal/` | private `cache.py` + `rate_limiter.py` (token-bucket) — not public API |

## Conventions

- Commits: `[feat|fix|refactor|docs|test|chore](scope): description`.
- Tests: `test_should_<expected_behavior>` (platform convention; the suite
  currently has legacy `test_*` names — new tests should follow the convention).
- LLM access is via the `LLMCallable` protocol — keep providers injectable, never
  hardcode a vendor.

## Release (GATED)

Versioned in `pyproject.toml` + `CHANGELOG.md` (Keep a Changelog). Publishing to
PyPI is a deliberate, **gated** step — not automatic on merge. Keep
`pyproject.version`, the CHANGELOG top entry, and the published PyPI version in
sync. Do not tag/publish without an explicit go-ahead.

## Known issues / gotchas

- **2 pre-existing ruff issues** (`UP042`): `CitationStyle` and `SourceType` in
  `citations/formatter.py` inherit `(str, Enum)`; ruff suggests `enum.StrEnum`.
  Left as-is intentionally (a later tier). `UP046` (PEP 695 generics) is
  surfaced by the py312 target on `_internal/cache.py:TTLCache` and is
  `ignore`d in `pyproject.toml` alongside this same modernization batch.
- **6 pre-existing mypy errors** (`mypy` is `strict`, not yet green): 4 ×
  `dict[str, object]` vs httpx `params` in `search/brave.py` + `search/academic.py`,
  1 unused `type: ignore` in `export/service.py`, 1 `no-any-return` in
  `analysis/summary.py`. Treat the type pass as advisory until cleaned up.
- See `AGENT_HANDOVER.md` for current state and next priorities.
