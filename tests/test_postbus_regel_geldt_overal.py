"""De postbus-uitzondering moet in ELK pad gelden, niet in drie losse kopieën.

"Een postbus houdt zijn postcode": `Postbus 250, 6800 GD Arnhem` is het
contactadres van een overheid, geen woonadres. Wegredigeren maakt een besluit
onleesbaar zonder iemand te beschermen.

Die regel stond in `find_deterministic()` en in `redact_postcode()`, maar niet
in `substitute()` — en juist `substitute()` is wat beide échte pijplijnen
aanroepen. Gemeten op het corpus op 2026-09-14: 304 postbus-regels, waarvan 214
met een vervángen postcode en precies één met een leesbare.

Het venijn zat in de meting. Mijn eigen controle liep via `find_deterministic()`
en meldde dus keurig dat de uitzondering werkte. Een regel op drie plekken is
geen regel maar drie regels die toevallig op elkaar lijken; deze test loopt
daarom álle paden langs.
"""
from __future__ import annotations


from wordsworth import detectors
from wordsworth.anonymizer import DeterministicAnonymizer

POSTBUS = "Postbus 250, 6800 GD Arnhem"
WOONADRES = "Burgemeester de Bordesstraat 80, 1404 GZ Bussum"


def test_de_regel_zit_in_de_gedeelde_definitie():
    """Niet per pad opnieuw bedacht, maar één keer vastgelegd."""
    per_label = {label: context for label, _p, _v, context in detectors.DETECTORS}
    assert per_label["postcode"] is detectors._postcode_context
    assert per_label["bsn"] is None        # alleen postcode heeft een contextregel


def test_find_deterministic_laat_de_postbus_staan():
    labels = [l for l, *_ in detectors.find_deterministic(POSTBUS)]
    assert "postcode" not in labels
    assert "postcode" in [l for l, *_ in detectors.find_deterministic(WOONADRES)]


def test_redact_postcode_laat_de_postbus_staan():
    uit, n = detectors.redact_postcode(POSTBUS)
    assert uit == POSTBUS and n == 0
    uit, n = detectors.redact_postcode(WOONADRES)
    assert "[POSTCODE]" in uit and n == 1


def test_de_irreversibele_pijplijn_laat_de_postbus_staan():
    """Dit pad paste de regel niet toe; het draaide via substitute()."""
    uit = DeterministicAnonymizer().anonymize(POSTBUS).text
    assert "6800 GD" in uit, "postbus-postcode werd alsnog geredigeerd"
    assert "[POSTCODE]" not in uit

    uit = DeterministicAnonymizer().anonymize(WOONADRES).text
    assert "1404 GZ" not in uit and "[POSTCODE]" in uit


def test_de_reversibele_pijplijn_laat_de_postbus_staan(session):
    """Het pad dat in productie draait — hier ging het 214 keer mis."""
    from wordsworth.keys import InMemoryKeyProvider
    from wordsworth.mapping_store import PostgresMappingStore
    from wordsworth.pseudonymizer import Pseudonymizer

    anon = Pseudonymizer(InMemoryKeyProvider(), PostgresMappingStore(session))
    uit = anon.anonymize(POSTBUS).text
    assert "6800 GD" in uit, "postbus-postcode werd alsnog gepseudonimiseerd"
    assert "[POSTCODE:" not in uit

    uit = anon.anonymize(WOONADRES).text
    assert "1404 GZ" not in uit and "[POSTCODE:" in uit


def test_een_briefhoofd_met_pijp_scheiding_telt_ook_als_postbus():
    """Briefhoofden zetten hun regels vaak naast elkaar met een pijp.

    `Postbus 2341 | 1234 AB Arnhem` viel buiten de contextregel, want die
    verwachtte een komma, punt of witruimte tussen nummer en postcode. Gemeten
    op het corpus: 19 van zulke regels werden alsnog geredigeerd.
    """
    from wordsworth.anonymizer import DeterministicAnonymizer

    pijp = "Postbus 2341 | 6800 GD Arnhem"
    assert detectors.redact_postcode(pijp) == (pijp, 0)
    assert "6800 GD" in DeterministicAnonymizer().anonymize(pijp).text

    # en een woonadres met dezelfde pijp blijft gewoon geredigeerd worden
    woon = "Brinklaan 35 | 1404 GZ Bussum"
    uit, n = detectors.redact_postcode(woon)
    assert n == 1 and "[POSTCODE]" in uit
