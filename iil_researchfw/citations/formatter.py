"""Citation management — APA, MLA, Chicago, Harvard, IEEE, Vancouver."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from iil_researchfw.core.exceptions import CitationError


def _user_agent() -> str:
    from iil_researchfw import __version__
    return f"iil-researchfw/{__version__} (research@iil.pet)"

logger = logging.getLogger(__name__)


class CitationStyle(str, Enum):
    APA = "apa"
    MLA = "mla"
    CHICAGO = "chicago"
    HARVARD = "harvard"
    IEEE = "ieee"
    VANCOUVER = "vancouver"


class SourceType(str, Enum):
    JOURNAL = "journal"
    BOOK = "book"
    CHAPTER = "chapter"
    CONFERENCE = "conference"
    THESIS = "thesis"
    WEBSITE = "website"
    PREPRINT = "preprint"
    REPORT = "report"


@dataclass
class Author:
    family: str
    given: str = ""
    suffix: str = ""
    orcid: str = ""

    def format_apa(self) -> str:
        if self.given:
            initials = ". ".join(p[0] for p in self.given.split()) + "."
            return f"{self.family}, {initials}"
        return self.family

    def format_mla(self) -> str:
        return f"{self.family}, {self.given}" if self.given else self.family

    def format_ieee(self) -> str:
        if self.given:
            initials = ". ".join(p[0] for p in self.given.split()) + "."
            return f"{initials} {self.family}"
        return self.family

    def full_name(self) -> str:
        return " ".join(p for p in [self.given, self.family, self.suffix] if p)


@dataclass
class Citation:
    title: str
    authors: list[Author] = field(default_factory=list)
    year: int | None = None
    source_type: SourceType = SourceType.JOURNAL
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    publisher: str = ""
    place: str = ""
    doi: str = ""
    url: str = ""
    accessed: str = ""
    edition: str = ""
    editor: str = ""
    book_title: str = ""
    institution: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def format(self, style: CitationStyle = CitationStyle.APA) -> str:
        method = getattr(self, f"_format_{style.value}", None)
        return method() if method else self._format_apa()

    def format_in_text(self, style: CitationStyle = CitationStyle.APA) -> str:
        year = self.year or "n.d."
        if not self.authors:
            return f"({self.title[:30]}, {year})"
        first = self.authors[0].family
        if len(self.authors) == 1:
            return f"({first}, {year})"
        if len(self.authors) == 2:
            return f"({first} & {self.authors[1].family}, {year})"
        return f"({first} et al., {year})"

    def _format_apa(self) -> str:
        authors_str = ", ".join(a.format_apa() for a in self.authors[:20])
        year = f"({self.year})" if self.year else "(n.d.)"
        doi_str = f" https://doi.org/{self.doi}" if self.doi else (f" {self.url}" if self.url else "")
        if self.source_type == SourceType.JOURNAL:
            vol = f", *{self.volume}*" if self.volume else ""
            iss = f"({self.issue})" if self.issue else ""
            pgs = f", {self.pages}" if self.pages else ""
            return f"{authors_str} {year}. {self.title}. *{self.journal}*{vol}{iss}{pgs}.{doi_str}"
        if self.source_type == SourceType.BOOK:
            return f"{authors_str} {year}. *{self.title}*. {self.publisher}.{doi_str}"
        return f"{authors_str} {year}. {self.title}.{doi_str}"

    def _format_mla(self) -> str:
        if self.authors:
            first = self.authors[0].format_mla()
            rest = [a.full_name() for a in self.authors[1:]]
            authors_str = first + (", and " + ", and ".join(rest) if rest else "")
        else:
            authors_str = ""
        year = str(self.year) if self.year else "n.d."
        if self.source_type == SourceType.JOURNAL:
            vol = f"vol. {self.volume}, " if self.volume else ""
            iss = f"no. {self.issue}, " if self.issue else ""
            pgs = f"pp. {self.pages}" if self.pages else ""
            return f'{authors_str}. "{self.title}." *{self.journal}*, {vol}{iss}{year}, {pgs}.'
        return f'{authors_str}. *{self.title}*. {self.publisher}, {year}.'

    def _format_chicago(self) -> str:
        if self.authors:
            first = self.authors[0].format_mla()
            rest = [a.full_name() for a in self.authors[1:]]
            authors_str = first + (", and " + ", and ".join(rest) if rest else "")
        else:
            authors_str = ""
        year = str(self.year) if self.year else "n.d."
        doi_str = f" https://doi.org/{self.doi}." if self.doi else "."
        if self.source_type == SourceType.JOURNAL:
            vol = f" {self.volume}" if self.volume else ""
            iss = f", no. {self.issue}" if self.issue else ""
            pgs = f": {self.pages}" if self.pages else ""
            return f'{authors_str}. "{self.title}." *{self.journal}*{vol}{iss} ({year}){pgs}{doi_str}'
        return f"{authors_str}. *{self.title}*. {self.place}: {self.publisher}, {year}{doi_str}"

    def _format_harvard(self) -> str:
        authors_str = ", ".join(a.format_apa() for a in self.authors)
        year = str(self.year) if self.year else "n.d."
        doi_str = f" doi:{self.doi}" if self.doi else ""
        if self.source_type == SourceType.JOURNAL:
            vol = f", {self.volume}" if self.volume else ""
            iss = f"({self.issue})" if self.issue else ""
            pgs = f", pp. {self.pages}" if self.pages else ""
            return f"{authors_str} ({year}) '{self.title}', *{self.journal}*{vol}{iss}{pgs}.{doi_str}"
        return f"{authors_str} ({year}) *{self.title}*. {self.publisher}.{doi_str}"

    def _format_ieee(self) -> str:
        authors_str = ", ".join(a.format_ieee() for a in self.authors)
        year = str(self.year) if self.year else "n.d."
        doi_str = f" doi: {self.doi}." if self.doi else "."
        if self.source_type == SourceType.JOURNAL:
            vol = f", vol. {self.volume}" if self.volume else ""
            iss = f", no. {self.issue}" if self.issue else ""
            pgs = f", pp. {self.pages}" if self.pages else ""
            return f'{authors_str}, "{self.title}," *{self.journal}*{vol}{iss}{pgs}, {year}{doi_str}'
        return f'{authors_str}, *{self.title}*, {self.publisher}, {year}{doi_str}'

    def _format_vancouver(self) -> str:
        authors_str = ", ".join(a.format_apa() for a in self.authors)
        year = str(self.year) if self.year else "n.d."
        doi_str = f" doi:{self.doi}" if self.doi else ""
        if self.source_type == SourceType.JOURNAL:
            vol = f";{self.volume}" if self.volume else ""
            iss = f"({self.issue})" if self.issue else ""
            pgs = f":{self.pages}" if self.pages else ""
            return f"{authors_str}. {self.title}. {self.journal}. {year}{vol}{iss}{pgs}{doi_str}"
        return f"{authors_str}. {self.title}. {self.publisher}; {year}{doi_str}"

    def to_bibtex(self) -> str:
        key = f"{self.authors[0].family.lower() if self.authors else 'unknown'}{self.year or ''}"
        lines = [f"@article{{{key},"]
        lines.append(f"  title = {{{self.title}}},")
        if self.authors:
            lines.append(f"  author = {{{ ' and '.join(a.full_name() for a in self.authors)}}},")
        if self.year:
            lines.append(f"  year = {{{self.year}}},")
        if self.journal:
            lines.append(f"  journal = {{{self.journal}}},")
        if self.volume:
            lines.append(f"  volume = {{{self.volume}}},")
        if self.issue:
            lines.append(f"  number = {{{self.issue}}},")
        if self.pages:
            lines.append(f"  pages = {{{self.pages}}},")
        if self.doi:
            lines.append(f"  doi = {{{self.doi}}},")
        if self.url:
            lines.append(f"  url = {{{self.url}}},")
        lines.append("}")
        return "\n".join(lines)

    def to_ris(self) -> str:
        type_map = {
            SourceType.JOURNAL: "JOUR", SourceType.BOOK: "BOOK",
            SourceType.CHAPTER: "CHAP", SourceType.CONFERENCE: "CONF",
            SourceType.THESIS: "THES", SourceType.WEBSITE: "ELEC",
            SourceType.PREPRINT: "UNPB", SourceType.REPORT: "RPRT",
        }
        lines = [f"TY  - {type_map.get(self.source_type, 'GEN')}"]
        lines.append(f"TI  - {self.title}")
        for a in self.authors:
            lines.append(f"AU  - {a.family}, {a.given}")
        if self.year:
            lines.append(f"PY  - {self.year}")
        if self.journal:
            lines.append(f"JO  - {self.journal}")
        if self.volume:
            lines.append(f"VL  - {self.volume}")
        if self.issue:
            lines.append(f"IS  - {self.issue}")
        if self.pages:
            start, *end = self.pages.split("-", 1)
            lines.append(f"SP  - {start}")
            if end:
                lines.append(f"EP  - {end[0]}")
        if self.doi:
            lines.append(f"DO  - {self.doi}")
        if self.url:
            lines.append(f"UR  - {self.url}")
        lines.append("ER  - ")
        return "\n".join(lines)


class CitationService:
    """Resolve and format citations from DOIs."""

    async def from_doi(self, doi: str) -> Citation | None:
        """Resolve a DOI via CrossRef API."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://api.crossref.org/works/{doi}",
                    headers={"User-Agent": _user_agent()},
                )
                if response.status_code != 200:
                    return None
                data = response.json().get("message", {})
        except httpx.HTTPError as exc:
            raise CitationError(f"Failed to resolve DOI {doi}: {exc}") from exc
        return self._parse_crossref(data, doi)

    def _parse_crossref(self, data: dict[str, Any], doi: str) -> Citation:
        authors = [
            Author(
                family=a.get("family", ""),
                given=a.get("given", ""),
                orcid=a.get("ORCID", "").split("/")[-1] if a.get("ORCID") else "",
            )
            for a in data.get("author", [])
        ]
        year = None
        pub = data.get("published") or data.get("published-print") or data.get("issued")
        if pub and pub.get("date-parts"):
            year = pub["date-parts"][0][0]
        source_type = SourceType.JOURNAL
        ct = data.get("type", "")
        if ct == "book":
            source_type = SourceType.BOOK
        elif ct == "book-chapter":
            source_type = SourceType.CHAPTER
        elif ct in ("proceedings-article", "conference-paper"):
            source_type = SourceType.CONFERENCE
        titles = data.get("title", ["Unknown"])
        journals = data.get("container-title", [""])
        return Citation(
            title=titles[0] if titles else "Unknown",
            authors=authors, year=year, source_type=source_type,
            journal=journals[0] if journals else "",
            volume=data.get("volume", ""), issue=data.get("issue", ""),
            pages=data.get("page", ""), publisher=data.get("publisher", ""),
            doi=doi, url=data.get("URL", ""),
            abstract=(data.get("abstract", "") or "")[:500],
            raw=data,
        )

    def format_bibliography(
        self, citations: list[Citation], style: CitationStyle = CitationStyle.APA
    ) -> str:
        sorted_citations = sorted(
            citations,
            key=lambda c: (c.authors[0].family.lower() if c.authors else c.title.lower()),
        )
        return "\n\n".join(c.format(style) for c in sorted_citations)

    async def from_isbn(self, isbn: str) -> Citation | None:
        """Resolve an ISBN (10 or 13) via OpenLibrary API."""
        isbn_clean = isbn.replace("-", "").replace(" ", "")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}"
                    f"&format=json&jscmd=data",
                    headers={"User-Agent": _user_agent()},
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                book = data.get(f"ISBN:{isbn_clean}")
                if not book:
                    return None
        except httpx.HTTPError as exc:
            raise CitationError(f"Failed to resolve ISBN {isbn}: {exc}") from exc
        return self._parse_openlibrary(book, isbn_clean)

    def _parse_openlibrary(self, data: dict[str, Any], isbn: str) -> Citation:
        authors = [
            Author(family=a.get("name", "").split()[-1], given=" ".join(a.get("name", "").split()[:-1]))
            for a in data.get("authors", [])
        ]
        publishers = data.get("publishers", [{}])
        pub_name = publishers[0].get("name", "") if publishers else ""
        publish_places = data.get("publish_places", [{}])
        place = publish_places[0].get("name", "") if publish_places else ""
        year = None
        publish_date = data.get("publish_date", "")
        for part in publish_date.split():
            if part.isdigit() and len(part) == 4:
                year = int(part)
                break
        subjects = data.get("subjects", [])
        keywords = [s.get("name", "") for s in subjects[:5]] if subjects else []
        return Citation(
            title=data.get("title", "Unknown"),
            authors=authors,
            year=year,
            source_type=SourceType.BOOK,
            publisher=pub_name,
            place=place,
            url=data.get("url", ""),
            keywords=keywords,
            raw=data,
        )

    @staticmethod
    def parse_bibtex(bibtex_str: str) -> list[Citation]:
        """
        Parse a BibTeX string and return a list of Citation objects.

        Supports: @article, @book, @inproceedings, @incollection,
                  @phdthesis, @mastersthesis, @techreport, @misc, @unpublished.

        Example::

            citations = CitationService.parse_bibtex(open("refs.bib").read())
        """
        import re

        citations: list[Citation] = []
        type_map = {
            "article": SourceType.JOURNAL,
            "book": SourceType.BOOK,
            "inproceedings": SourceType.CONFERENCE,
            "conference": SourceType.CONFERENCE,
            "incollection": SourceType.CHAPTER,
            "phdthesis": SourceType.THESIS,
            "mastersthesis": SourceType.THESIS,
            "techreport": SourceType.REPORT,
            "misc": SourceType.WEBSITE,
            "unpublished": SourceType.PREPRINT,
        }
        entry_pattern = re.compile(
            r"@(\w+)\s*\{([^,]+),\s*(.*?)\n\}", re.DOTALL | re.IGNORECASE
        )
        field_pattern = re.compile(
            r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}", re.DOTALL
        )
        for entry_match in entry_pattern.finditer(bibtex_str):
            entry_type = entry_match.group(1).lower()
            fields_str = entry_match.group(3)
            fields: dict[str, str] = {
                k.lower(): v.strip()
                for k, v in field_pattern.findall(fields_str)
            }
            source_type = type_map.get(entry_type, SourceType.JOURNAL)
            raw_authors = fields.get("author", "")
            authors: list[Author] = []
            if raw_authors:
                for raw in re.split(r"\s+and\s+", raw_authors, flags=re.IGNORECASE):
                    raw = raw.strip()
                    if "," in raw:
                        parts = [p.strip() for p in raw.split(",", 1)]
                        authors.append(Author(family=parts[0], given=parts[1] if len(parts) > 1 else ""))
                    else:
                        parts_list = raw.split()
                        if parts_list:
                            authors.append(Author(family=parts_list[-1], given=" ".join(parts_list[:-1])))
            year_str = fields.get("year", "")
            year = int(year_str) if year_str.isdigit() else None
            pages = fields.get("pages", "").replace("--", "-")
            keywords_raw = fields.get("keywords", "")
            keywords = [k.strip() for k in re.split(r"[,;]", keywords_raw) if k.strip()]
            citations.append(Citation(
                title=fields.get("title", "Unknown"),
                authors=authors,
                year=year,
                source_type=source_type,
                journal=fields.get("journal", "") or fields.get("booktitle", ""),
                volume=fields.get("volume", ""),
                issue=fields.get("number", ""),
                pages=pages,
                publisher=fields.get("publisher", "") or fields.get("school", ""),
                place=fields.get("address", ""),
                doi=fields.get("doi", ""),
                url=fields.get("url", ""),
                edition=fields.get("edition", ""),
                editor=fields.get("editor", ""),
                abstract=fields.get("abstract", "")[:500],
                keywords=keywords,
                raw=fields,
            ))
        return citations

    def export_bibtex(self, citations: list[Citation]) -> str:
        return "\n\n".join(c.to_bibtex() for c in citations)

    def export_ris(self, citations: list[Citation]) -> str:
        return "\n\n".join(c.to_ris() for c in citations)
