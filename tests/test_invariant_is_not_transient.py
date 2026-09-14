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
