"""Academic search — async concurrent multi-source."""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from iil_researchfw._internal.cache import TTLCache
from iil_researchfw.core.exceptions import RateLimitError
from iil_researchfw.search.base import AsyncBaseSearchProvider

logger = logging.getLogger(__name__)


@dataclass
class AcademicPaper:
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    url: str = ""
    source: str = ""
    doi: str | None = None
    arxiv_id: str | None = None
    publication_date: str = ""
    journal: str = ""
    citation_count: int | None = None
    pdf_url: str | None = None
    categories: list[str] = field(default_factory=list)


class AcademicSearchService(AsyncBaseSearchProvider):
    """
    Concurrent multi-source academic search.

    All source calls run in parallel via asyncio.gather().
    Per-source failures are isolated — partial results are returned.
    """

    def __init__(self, cache_ttl_seconds: int = 3600) -> None:
        self._cache: TTLCache[list[AcademicPaper]] = TTLCache(ttl_seconds=cache_ttl_seconds)

    async def search(
        self,
        query: str,
        sources: list[str] | None = None,
        max_results: int = 10,
        **kwargs: Any,
    ) -> list[AcademicPaper]:
        """Concurrent search across all academic sources."""
        active = sources or ["arxiv", "semantic_scholar", "pubmed", "openalex"]
        cache_key = TTLCache.make_key(query, sorted(active), max_results)
        if cached := self._cache.get(cache_key):
            return cached

        async with httpx.AsyncClient(timeout=15.0) as client:
            tasks = []
            source_names: list[str] = []
            for src in active:
                fn = getattr(self, f"_search_{src}", None)
                if fn is not None:
                    tasks.append(fn(client, query, max_results))
                    source_names.append(src)

            results = await asyncio.gather(*tasks, return_exceptions=True)

        papers: list[AcademicPaper] = []
        for src, result in zip(source_names, results):
            if isinstance(result, Exception):
                logger.warning("%s search failed: %s", src, result)
            else:
                papers.extend(result)  # type: ignore[arg-type]

        deduped = self._deduplicate(papers)[:max_results]
        self._cache.set(cache_key, deduped)
        return deduped

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    async def _search_arxiv(
        self, client: httpx.AsyncClient, query: str, max_results: int
    ) -> list[AcademicPaper]:
        """arXiv XML API — no API key required."""
        params = {"search_query": f"all:{query}", "start": 0, "max_results": min(max_results, 100)}
        response = await client.get("https://export.arxiv.org/api/query", params=params)
        if response.status_code == 429:
            raise RateLimitError("arxiv", 429)
        response.raise_for_status()
        return self._parse_arxiv_xml(response.text)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    async def _search_semantic_scholar(
        self, client: httpx.AsyncClient, query: str, max_results: int
    ) -> list[AcademicPaper]:
        """Semantic Scholar API — free, 100 req/5min."""
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": "title,authors,abstract,year,externalIds,openAccessPdf,citationCount",
        }
        response = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search", params=params
        )
        if response.status_code == 429:
            raise RateLimitError("semantic_scholar", 429)
        response.raise_for_status()
        return self._parse_semantic_scholar(response.json())

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=15),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    async def _search_pubmed(
        self, client: httpx.AsyncClient, query: str, max_results: int
    ) -> list[AcademicPaper]:
        """NCBI E-utilities — free, 3 req/sec without API key."""
        r = await client.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": min(max_results, 10000), "retmode": "json"},
        )
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])[:max_results]
        if not ids:
            return []
        r2 = await client.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
        )
        r2.raise_for_status()
        return self._parse_pubmed_xml(r2.text)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    async def _search_openalex(
        self, client: httpx.AsyncClient, query: str, max_results: int
    ) -> list[AcademicPaper]:
        """OpenAlex API — free, 100k req/day."""
        response = await client.get(
            "https://api.openalex.org/works",
            params={"search": query, "per_page": min(max_results, 50), "mailto": "research@iil.pet"},
        )
        response.raise_for_status()
        return self._parse_openalex(response.json())

    async def get_paper_by_doi(self, doi: str) -> AcademicPaper | None:
        """Lookup a paper by DOI via CrossRef."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"https://api.crossref.org/works/{doi}")
            if response.status_code != 200:
                return None
            data = response.json().get("message", {})
        return AcademicPaper(
            title=" ".join(data.get("title", ["Unknown"])),
            authors=[
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in data.get("author", [])
            ],
            doi=doi,
            url=f"https://doi.org/{doi}",
            source="crossref",
            journal=data.get("container-title", [""])[0] if data.get("container-title") else "",
            publication_date=str(data.get("published", {}).get("date-parts", [[""]])[0][0]),
        )

    def _parse_arxiv_xml(self, xml_text: str) -> list[AcademicPaper]:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_text)
        papers = []
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
            authors = [a.findtext("atom:name", "", ns) or "" for a in entry.findall("atom:author", ns)]
            abstract = (entry.findtext("atom:summary", "", ns) or "").strip()
            url = entry.findtext("atom:id", "", ns) or ""
            arxiv_id = url.split("/abs/")[-1] if "/abs/" in url else None
            papers.append(AcademicPaper(
                title=title, authors=authors, abstract=abstract[:500],
                url=url, source="arxiv", arxiv_id=arxiv_id,
            ))
        return papers

    def _parse_semantic_scholar(self, data: dict[str, Any]) -> list[AcademicPaper]:
        return [
            AcademicPaper(
                title=item.get("title", ""),
                authors=[a.get("name", "") for a in item.get("authors", [])],
                abstract=item.get("abstract", "") or "",
                url=f"https://api.semanticscholar.org/paper/{item.get('paperId', '')}",
                source="semantic_scholar",
                doi=item.get("externalIds", {}).get("DOI"),
                publication_date=str(item.get("year", "")),
                citation_count=item.get("citationCount"),
                pdf_url=(item.get("openAccessPdf") or {}).get("url"),
            )
            for item in data.get("data", [])
        ]

    def _parse_pubmed_xml(self, xml_text: str) -> list[AcademicPaper]:
        root = ET.fromstring(xml_text)
        papers = []
        for article in root.findall(".//PubmedArticle"):
            papers.append(AcademicPaper(
                title=article.findtext(".//ArticleTitle", "") or "",
                authors=[
                    f"{a.findtext('LastName', '')} {a.findtext('ForeName', '')}".strip()
                    for a in article.findall(".//Author")
                    if a.findtext("LastName")
                ],
                abstract=(article.findtext(".//AbstractText", "") or "")[:500],
                url=f"https://pubmed.ncbi.nlm.nih.gov/{article.findtext('.//PMID', '')}/",
                source="pubmed",
                publication_date=article.findtext(".//PubDate/Year", "") or "",
                journal=article.findtext(".//Journal/Title", "") or "",
            ))
        return papers

    def _parse_openalex(self, data: dict[str, Any]) -> list[AcademicPaper]:
        papers = []
        for item in data.get("results", []):
            doi = item.get("doi", "")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi[16:]
            loc = item.get("primary_location") or {}
            src = loc.get("source") or {}
            oa = item.get("open_access", {})
            papers.append(AcademicPaper(
                title=item.get("title") or "Unknown",
                authors=[
                    auth.get("author", {}).get("display_name", "")
                    for auth in item.get("authorships", [])[:10]
                ],
                url=item.get("id", ""),
                source="openalex",
                doi=doi or None,
                publication_date=str(item.get("publication_year", "")),
                journal=src.get("display_name", ""),
                citation_count=item.get("cited_by_count"),
                pdf_url=oa.get("oa_url") if oa.get("is_oa") else None,
            ))
        return papers

    def _deduplicate(self, papers: list[AcademicPaper]) -> list[AcademicPaper]:
        seen_dois: set[str] = set()
        seen_titles: set[str] = set()
        result = []
        for p in papers:
            if p.doi and p.doi in seen_dois:
                continue
            norm = p.title.lower().strip()
            if norm in seen_titles:
                continue
            if p.doi:
                seen_dois.add(p.doi)
            seen_titles.add(norm)
            result.append(p)
        return result
