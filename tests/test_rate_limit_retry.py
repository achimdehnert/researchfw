"""Der Wiederholungsversuch greift auch bei 429 — nicht nur bei anderen HTTP-Fehlern.

Bis 2026-08-06 fingen die Decorator in ``academic.py`` ausschliesslich
``httpx.HTTPStatusError``. Die Registerfunktionen werfen bei 429 aber
``RateLimitError``, und zwar **vor** ``raise_for_status()`` — und
``RateLimitError`` stammt von ``ResearchError``, nicht von httpx. Der
Mechanismus feuerte damit ausgerechnet fuer den Fall nicht, fuer den er dem
Namen nach da ist.

Belegt wurde das durch einen A/B-Vergleich in writing-hub#517: gleicher Code,
gleiche vier Suchbegriffe, nur ein anderer Antwortstatus.

    403 (=> HTTPStatusError)  ->  12 Anfragen  =  3 Versuche je Begriff
    429 (=> RateLimitError)   ->   4 Anfragen  =  1 Versuch  je Begriff

Praktische Folge: ein einziger 429 beendete das Register fuer den gesamten Lauf.
Im Messlauf fielen 2 von 4 Begriffen aus, die der vorhandene Backoff
(1 s, dann 2 s) mit hoher Wahrscheinlichkeit gerettet haette.
"""

import httpx
import pytest
from tenacity import RetryError

from iil_researchfw.core.exceptions import RateLimitError
from iil_researchfw.search import academic


class TreiberZaehler:
    """Ein Aufrufzaehler, der die ersten ``n`` Male scheitert."""

    def __init__(self, fehler: Exception, fehlschlaege: int):
        self.fehler = fehler
        self.uebrig = fehlschlaege
        self.aufrufe = 0

    async def __call__(self, *args, **kwargs):
        self.aufrufe += 1
        if self.uebrig > 0:
            self.uebrig -= 1
            raise self.fehler
        return "ok"


# ── Die Klassenlage, aus der der Defekt entstand ────────────────────────────


def test_should_confirm_rate_limit_error_is_not_an_httpx_error():
    """Der Kern des Defekts, als Tatsache festgehalten.

    Waere ``RateLimitError`` eine httpx-Ausnahme, haette der alte Decorator
    funktioniert und dieser ganze Fix waere unnoetig.
    """
    assert not issubclass(RateLimitError, httpx.HTTPStatusError)


def test_should_list_both_error_kinds_as_retryable():
    assert httpx.HTTPStatusError in academic.WIEDERHOLBAR
    assert RateLimitError in academic.WIEDERHOLBAR


# ── Verhalten: beide Fehlerarten werden wiederholt ──────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fehler",
    [
        pytest.param(RateLimitError("semantic_scholar", 429), id="429-RateLimitError"),
        pytest.param(
            httpx.HTTPStatusError(
                "boom", request=httpx.Request("GET", "https://x"), response=httpx.Response(403)
            ),
            id="403-HTTPStatusError",
        ),
    ],
)
async def test_should_retry_until_it_succeeds(fehler):
    """Zwei Fehlschlaege, dann Erfolg — also drei Aufrufe.

    Der 429-Fall ist der Anlassfall: vor dem Fix blieb es bei EINEM Aufruf.
    """
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

    treiber = TreiberZaehler(fehler, fehlschlaege=2)
    umhuellt = retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(0),
        retry=retry_if_exception_type(academic.WIEDERHOLBAR),
    )(treiber)

    assert await umhuellt() == "ok"
    assert treiber.aufrufe == 3


@pytest.mark.asyncio
async def test_should_prove_the_old_filter_would_not_have_retried_a_429():
    """Gegenprobe gegen den ALTEN Zustand.

    Ohne sie belegt der Test oben nur, dass tenacity tut was es soll — nicht,
    dass die Aenderung ein echtes Problem behebt.
    """
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

    treiber = TreiberZaehler(RateLimitError("semantic_scholar", 429), fehlschlaege=2)
    alt = retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(0),
        retry=retry_if_exception_type(httpx.HTTPStatusError),  # der Stand bis 2026-08-06
    )(treiber)

    with pytest.raises(RateLimitError):
        await alt()
    assert treiber.aufrufe == 1, "Der alte Filter haette den 429 doch wiederholt — Annahme falsch"


@pytest.mark.asyncio
async def test_should_give_up_after_the_configured_attempts():
    """Wiederholen heisst nicht ewig — sonst haengt ein Lauf an einem toten Register."""
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

    treiber = TreiberZaehler(RateLimitError("semantic_scholar", 429), fehlschlaege=99)
    umhuellt = retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(0),
        retry=retry_if_exception_type(academic.WIEDERHOLBAR),
    )(treiber)

    with pytest.raises(RetryError):
        await umhuellt()
    assert treiber.aufrufe == 3


# ── Alle Register, nicht nur das auffaellige ────────────────────────────────


def test_should_apply_the_filter_to_every_register_function():
    """Semantic Scholar fiel auf, arXiv hatte denselben Defekt still."""
    import ast
    import pathlib

    quelle = pathlib.Path(academic.__file__).read_text(encoding="utf-8")
    baum = ast.parse(quelle)

    betroffen = []
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.AsyncFunctionDef):
            continue
        deko = " ".join(ast.unparse(d) for d in knoten.decorator_list)
        if "retry_if_exception_type" not in deko:
            continue
        if "RateLimitError" not in ast.unparse(knoten):
            continue
        betroffen.append((knoten.name, "WIEDERHOLBAR" in deko))

    assert betroffen, "Keine Registerfunktion mit Retry gefunden — der Test laeuft ins Leere"
    ohne = [name for name, ok in betroffen if not ok]
    assert not ohne, f"Diese Register wirft 429, wiederholt es aber nicht: {ohne}"
