# AGENT_HANDOVER — iil-researchfw

> Living handover for the next agent/session. Keep this current; `NEXT.md` is an
> auto-generated cache and is **not** the source of truth — this file is.

## Current state (2026-06-22)

- Version: **0.6.0** (`pyproject` + CHANGELOG top entry aligned).
- Tests: green — `make test` → **89 passed**; coverage ≈ **69%** (gate `fail_under = 65`).
- Lint: `ruff check .` → 2 pre-existing `UP042` suggestions (see below).
- Types: `mypy iil_researchfw` (strict) → 6 errors (advisory, not gated).
- CI: `ci.yml` (ruff + mypy + coverage on Python 3.12).

## Recently landed

- Agent-readiness (Tier 1): `__version__` now resolved from package metadata
  (was hardcoded), public-API submodule-map docstring in `__init__.py`,
  `CLAUDE.md`, `AGENT_HANDOVER.md`, `make types` target.
- Config alignment: ruff `target-version` + mypy `python_version` → `py312`, and
  Python classifiers trimmed to `3` / `3.12`, matching `requires-python >=3.12`.
- 0.6.0: citation-graph expansion (ADR-160 Phase 5) + iterative gap analysis
  (Phase 6) on `SmartSearchService`.

## Known issues / TODO

- **2 ruff `UP042`** in `citations/formatter.py`: `CitationStyle` and
  `SourceType` inherit `(str, Enum)`; ruff suggests `enum.StrEnum`. Deferred to a
  later tier (not fixed here). The py312 target also surfaced `UP046` (PEP 695
  generics) on `_internal/cache.py:TTLCache` — `ignore`d in `pyproject.toml`
  to keep the lint at the same 2 issues; migrate it in the same batch.
- **6 mypy errors** (strict, advisory): 4 × `dict[str, object]` vs httpx `params`
  (`search/brave.py:67`, `search/academic.py:97,122,326`), 1 unused
  `type: ignore` (`export/service.py:97`), 1 `no-any-return`
  (`analysis/summary.py:120`). Deferred to a later tier (not fixed here).
- Test names are legacy `test_*`, not the platform `test_should_*` convention.

## Next priorities

1. Migrate `CitationStyle` / `SourceType` to `enum.StrEnum` and `TTLCache` to
   PEP 695 generics, then drop the `UP042`/`UP046` ruff `ignore` (the Python 3.12
   floor now makes both safe).
2. Drive the 6 mypy errors to zero (type the httpx `params` dicts as
   `dict[str, str | int]`; drop the dead `type: ignore`; fix the `Any` return).
3. Rename tests to `test_should_<behavior>` as they are touched.

## Pointers

- Architecture + commands: `CLAUDE.md`.
- Extraction/design rationale: platform ADR-105; search features ADR-160.
- Changelog: `CHANGELOG.md` (Keep a Changelog).
