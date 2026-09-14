"""Een invariant die breekt is geen storing (pure unit, geen DB).

Beide soorten weigeren tekst uit te geven, en dat blijft zo. Het verschil zit in
wat de operator daarna moet doen. "De service is onbereikbaar" gaat vanzelf
over; "de service gaf een entiteit zonder score" en "een gedetecteerde waarde
overleefde de pseudonimisering" gaan niet over — dezelfde invoer ontmoet dezelfde
code en faalt identiek, voor altijd.

Gemeten op 2026-09-14: acht documenten werden run na run als `retryable`
gemeld. Dat waren ze niet. De run zag er herstelbaar uit terwijl er een
codewijziging nodig was, en elke poging kostte GLiNER-tijd om tot dezelfde
conclusie te komen.
"""
from __future__ import annotations

import httpx

from wordsworth.openanonymiser_driver import (
    AnonymizationEngineError,
    AnonymizationInvariantError,
)
from wordsworth.retry import is_transient


def test_een_onbereikbare_motor_is_tijdelijk():
    assert is_transient(AnonymizationEngineError("service weg")) is True


def test_een_gebroken_invariant_is_niet_tijdelijk():
    assert is_transient(AnonymizationInvariantError("waarde overleefde")) is False


def test_de_invariantfout_blijft_een_motorfout():
    """Subklasse, zodat elke bestaande `except AnonymizationEngineError` hem
    nog vangt — het fail-closed gedrag verandert niet, alleen het etiket."""
    assert issubclass(AnonymizationInvariantError, AnonymizationEngineError)
    try:
        raise AnonymizationInvariantError("x")
    except AnonymizationEngineError:
        pass
    else:
        raise AssertionError("werd niet gevangen als motorfout")


def test_transporte_fouten_blijven_tijdelijk():
    assert is_transient(httpx.ConnectTimeout("traag")) is True


def test_de_code_zegt_welke_invariant_brak():
    """Twee invariant-controles delen één klasse; de code onderscheidt ze.

    Zonder die code weet je na een mislukte run wél dat een invariant brak,
    maar niet welke — en dat is precies het verschil tussen "de motor hield
    zich niet aan het contract" en "onze eigen vervanging liet iets staan".
    """
    fout = AnonymizationInvariantError("x", code="waarde-overleefde-vervanging")
    assert fout.code == "waarde-overleefde-vervanging"
    assert is_transient(fout) is False


def test_zonder_code_valt_hij_terug_op_onbekend():
    assert AnonymizationInvariantError("x").code == "onbekend"


def test_de_kenmerken_dragen_nooit_een_waarde():
    """Wat de raise-site meegeeft moet type/lengte/aantal zijn, geen tekst.

    De audit-keten is exporteerbaar. Een 'handige' foutboodschap met de waarde
    erin is document-inhoud in een exporteerbaar spoor, en dat is precies wat
    deze hele laag moet voorkomen.
    """
    fout = AnonymizationInvariantError(
        "x", code="waarde-overleefde-vervanging",
        kenmerken={"label": "PERSON", "lengte": 9, "in_bron": 3,
                   "na_vervanging": 1, "woorden": 2, "alnum": False})
    assert set(fout.kenmerken) == {"label", "lengte", "in_bron",
                                   "na_vervanging", "woorden", "alnum"}
    assert all(isinstance(v, (int, bool, str)) for v in fout.kenmerken.values())
    assert fout.kenmerken["label"] in ("PERSON", "LOCATION", "ORGANIZATION",
                                       "DATE_TIME", "EMAIL", "PHONE_NUMBER",
                                       "BSN", "IBAN", "POSTCODE")


def test_zonder_kenmerken_is_het_een_lege_dict():
    assert AnonymizationInvariantError("x").kenmerken == {}
