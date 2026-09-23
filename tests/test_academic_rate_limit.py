"""Per-Quellen-Drossel in AcademicSearchService (writing-hub#1261 K2).

Kontext (gemessen im Konsumenten writing-hub, 2026-09-23): arXiv antwortete
406 auf parallele Mehrwort-Anfragen (36 Fehlschlaege in einem Lauf), Minuten
spaeter 200 auf dieselbe Anfrage — arXiv verlangt laut API-Terms hoechstens
eine Anfrage je 3 Sekunden. Semantic Scholar antwortete mit 429 (~1 req/s,
auch mit Schluessel).

Diese Tests belegen, ohne real zu warten (Zeit/Sleep gemockt) und ohne
echten Netzaufruf (``httpx.AsyncClient`` durch ``_FakeAsyncClient`` ersetzt):

1. der Mindestabstand je Quelle wird durchgesetzt (arXiv 3.0s Default),
2. verschiedene Quellen drosseln unabhaengig voneinander — keine Quelle
   wartet auf den Mindestabstand einer anderen (eigener ``RateLimiter`` je
   Quelle, kein geteilter Zustand),
3. 406 wird wie 429 wiederholt (``WIEDERHOLBAR``), bis die Anfrage durchgeht.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from iil_researchfw.search import academic as academic_module
from iil_researchfw.search.academic import DEFAULT_RATE_LIMITS, AcademicSearchService
from tests.conftest import ARXIV_XML_FIXTURE, SEMANTIC_SCHOLAR_FIXTURE


class _FakeAsyncClient:
    """Ersetzt ``httpx.AsyncClient`` — kein echter Netzaufruf.

    Merkt sich Quelle + Reihenfolge jedes ``get()`` in ``calls``. Fuer arXiv
    kann eine Statusfolge vorgegeben werden (z.B. ``[406, 406, 200]``); ist
    sie erschoepft, bleibt der letzte Wert stehen.
    """

    def __init__(self, arxiv_statuses: list[int] | None = None) -> None:
        self.calls: list[str] = []
        self._arxiv_statuses = list(arxiv_statuses or [200])

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def _next_arxiv_status(self) -> int:
        if len(self._arxiv_statuses) > 1:
            return self._arxiv_statuses.pop(0)
        return self._arxiv_statuses[0]

    async def get(
        self, url: str, params: dict | None = None, headers: dict | None = None
    ) -> httpx.Response:
        request = httpx.Request("GET", url, params=params or {})
        if "export.arxiv.org" in url:
            self.calls.append("arxiv")
            status = self._next_arxiv_status()
            text = ARXIV_XML_FIXTURE if status == 200 else ""
            return httpx.Response(status, text=text, request=request)
        if "semanticscholar.org" in url:
            self.calls.append("semantic_scholar")
            return httpx.Response(200, json=SEMANTIC_SCHOLAR_FIXTURE, request=request)
        if "openalex.org" in url:
            self.calls.append("openalex")
            return httpx.Response(200, json={"results": []}, request=request)
        if "ncbi.nlm.nih.gov" in url:
            self.calls.append("pubmed")
            return httpx.Response(200, json={"esearchresult": {"idlist": []}}, request=request)
        raise AssertionError(f"unerwartete URL im Test: {url}")


@pytest.mark.asyncio
async def test_should_enforce_minimum_interval_between_arxiv_requests(monkeypatch):
    """Zwei arXiv-Anfragen erzwingen den Default-Mindestabstand (3.0s).

    Zeit gemockt: eine feste Uhr laesst beide Anfragen "gleichzeitig"
    stattfinden, sodass der gesamte Mindestabstand ueber den gemockten
    ``asyncio.sleep`` eingefordert werden muss — kein reales Warten.
    """
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    fixed_time = 1_000_000.0
    monkeypatch.setattr("iil_researchfw._internal.rate_limiter.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("iil_researchfw._internal.rate_limiter.time.monotonic", lambda: fixed_time)

    client = _FakeAsyncClient()
    monkeypatch.setattr(academic_module.httpx, "AsyncClient", lambda *a, **k: client)

    service = AcademicSearchService(cache_ttl_seconds=0)
    await service.search("query one", sources=["arxiv"])
    await service.search("query two", sources=["arxiv"])

    assert DEFAULT_RATE_LIMITS["arxiv"] == 3.0
    assert sleep_calls == [pytest.approx(3.0)]
    assert client.calls == ["arxiv", "arxiv"]


@pytest.mark.asyncio
async def test_should_throttle_sources_independently(monkeypatch):
    """arXiv (3.0s) und Semantic Scholar (1.0s) drosseln unabhaengig.

    Gegenprobe eingebaut: mit einem faelschlich GETEILTEN Limiter saehen
    beide Wartezeiten im zweiten Durchlauf gleich aus (das zuerst gesetzte
    Intervall haette gewonnen) — hier muessen es 3.0s und 1.0s bleiben.
    """
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(round(seconds, 4))

    fixed_time = 2_000_000.0
    monkeypatch.setattr("iil_researchfw._internal.rate_limiter.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("iil_researchfw._internal.rate_limiter.time.monotonic", lambda: fixed_time)

    client = _FakeAsyncClient()
    monkeypatch.setattr(academic_module.httpx, "AsyncClient", lambda *a, **k: client)

    service = AcademicSearchService(cache_ttl_seconds=0)
    # Runde 1: beide Quellen frisch -> kein Warten noetig.
    await service.search("round one", sources=["arxiv", "semantic_scholar"])
    assert sleep_calls == []

    # Runde 2: beide muessten warten -- aber je Quelle unterschiedlich lang.
    await service.search("round two", sources=["arxiv", "semantic_scholar"])
    assert sorted(sleep_calls) == [1.0, 3.0]
    # Beide Anfragen liefen -- keine wurde von der anderen blockiert/verschluckt.
    assert client.calls.count("arxiv") == 2
    assert client.calls.count("semantic_scholar") == 2


@pytest.mark.asyncio
async def test_should_retry_arxiv_406_until_it_succeeds(monkeypatch):
    """406 (wie 429) wird wiederholt — arXivs Antwort auf zu dichte Anfragen.

    Sleep (Rate-Limiter UND tenacity-Backoff) gemockt, damit der Test nicht
    real ~3s Drossel + Backoff wartet.
    """

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    client = _FakeAsyncClient(arxiv_statuses=[406, 406, 200])
    monkeypatch.setattr(academic_module.httpx, "AsyncClient", lambda *a, **k: client)

    service = AcademicSearchService(cache_ttl_seconds=0)
    papers = await service.search("resilience test", sources=["arxiv"])

    assert client.calls.count("arxiv") == 3
    assert len(papers) == 1
    assert papers[0].source == "arxiv"


@pytest.mark.asyncio
async def test_should_accept_custom_rate_limits_via_constructor():
    """``rate_limits`` im Konstruktor ueberschreibt/ergaenzt die Defaults."""
    service = AcademicSearchService(cache_ttl_seconds=0, rate_limits={"arxiv": 5.0})
    assert service._rate_limits["arxiv"] == 5.0
    # Unbenannte Quellen behalten ihren Default.
    assert service._rate_limits["semantic_scholar"] == DEFAULT_RATE_LIMITS["semantic_scholar"]
    # Unbekannte Quellen ohne Eintrag bleiben ungedrosselt (Default 0.0).
    assert service._limiter("crossref").calls_per_second == float("inf")
