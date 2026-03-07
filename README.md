# iil-researchfw

**Platform research framework** — async search, citations, analysis, export.

[![PyPI](https://img.shields.io/pypi/v/iil-researchfw)](https://pypi.org/project/iil-researchfw/)
[![Python](https://img.shields.io/pypi/pyversions/iil-researchfw)](https://pypi.org/project/iil-researchfw/)
[![CI](https://github.com/achimdehnert/researchfw/actions/workflows/ci.yml/badge.svg)](https://github.com/achimdehnert/researchfw/actions)

## Features

- **Async-first**: `asyncio.gather()` für parallele API-Calls (arXiv, Semantic Scholar, PubMed, OpenAlex)
- **Brave Search**: Web-Search via Brave API
- **Citations**: APA, MLA, Chicago, Harvard, IEEE, Vancouver + BibTeX/RIS
- **AI Summary**: LLM-agnostisch via `LLMCallable` Protocol
- **Export**: Markdown, LaTeX, DOCX
- **Rate Limiting**: Token-Bucket per API-Endpoint
- **Retry**: `tenacity` Exponential Backoff

## Installation

```bash
pip install iil-researchfw
pip install iil-researchfw[export]     # + python-docx, markdown
pip install iil-researchfw[scraping]   # + beautifulsoup4, playwright
pip install iil-researchfw[all]        # alles
```

## Quick Start

```python
import asyncio
from iil_researchfw.search.academic import AcademicSearchService
from iil_researchfw.search.brave import BraveSearchService
from iil_researchfw.citations.formatter import CitationService, CitationStyle

async def main():
    # Academic Search
    academic = AcademicSearchService()
    papers = await academic.search("machine learning transformers", max_results=10)
    for p in papers:
        print(f"{p.title} — {p.source}")

    # Web Search
    brave = BraveSearchService(api_key="your-key")  # or BRAVE_API_KEY env var
    results = await brave.search("Python asyncio best practices")

    # Citations
    citations = CitationService()
    citation = await citations.from_doi("10.1145/3290605.3300233")
    print(citation.format(CitationStyle.APA))

asyncio.run(main())
```

## Architecture

See [ADR-105](https://github.com/achimdehnert/platform/blob/main/docs/adr/ADR-105-iil-researchfw-extraction-plan.md).

## License

MIT
