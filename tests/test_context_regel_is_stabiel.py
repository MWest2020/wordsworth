"""De contextregel mag niet van eerdere vervangingen afhangen.

De detectoren draaien op volgorde en herschrijven de tekst voor elkaar: tegen de
tijd dat de postcode aan de beurt is, staan er placeholders op de plek van
e-mailadressen, en die hebben een andere lengte. Een contextregel die alleen maar
veertig tekens terugkijkt zou daardoor van toeval afhangen.

Dat doet hij niet, en de reden zit in één teken: `_POSTBUS_RE` eindigt op `$`, dus
de markering moet PAL vóór de postcode staan. Staat hij daar in de bron, dan zat
er niets tussen, dus is er ook niets vervangen. En andersom kan een vervanging de
match nooit maken: een placeholder bevat `[`, wat niet in de scheidingstekens
`[,.\\s|]` zit, dus tussenliggende vervanging breekt hem juist.

Nagemeten op het Woo-corpus (2026-09-15): 1016 postcode-voorkomens in 627
documenten, en de regel gaf op de brontekst nul keer een ander antwoord dan op de
werktekst. Deze tests pinnen vast waaróm dat zo is, zodat het losmaken van die
verankering een bewuste daad wordt en geen bijvangst.
"""
from __future__ import annotations

from wordsworth import detectors
from wordsworth.anonymizer import DeterministicAnonymizer

POSTBUS = "Postbus 250, 6800 GD Arnhem"
MET_MAIL = "Vragen? info@gemeente-arnhem.nl\nPostbus 250, 6800 GD Arnhem"
# Dezelfde markering, maar niet pal ervoor: de regel hoort hier niet te gelden.
VER_WEG = "Postbus 16005\nKvK NL002169259B29\n3500 DA Utrecht"


def test_de_markering_moet_pal_voor_de_postcode_staan():
    """De verankering is dragend. Zonder de `$` hangt de regel van toeval af."""
    assert detectors._POSTBUS_RE.pattern.endswith("$"), (
        "de postbus-markering is niet meer aan het einde van het venster "
        "verankerd; daarmee kan een eerdere vervanging het antwoord veranderen"
    )
    # en dat is niet alleen vorm: het gedrag hoort erbij
    assert detectors._postcode_context("Postbus 250, ", len("Postbus 250, ")) is False
    assert detectors._postcode_context("Postbus 250, x ", len("Postbus 250, x ")) is True


def test_een_vervanging_ervoor_verandert_het_antwoord_niet():
    kaal = DeterministicAnonymizer().anonymize(POSTBUS).text
    met = DeterministicAnonymizer().anonymize(MET_MAIL).text
    assert "6800 GD" in kaal
    assert "6800 GD" in met, "de postcode ging alsnog weg door het e-mailadres"
    assert "[EMAIL]" in met                      # er is wél iets vervangen


def test_een_markering_verderop_telt_niet():
    uit = DeterministicAnonymizer().anonymize(VER_WEG).text
    assert "3500 DA" not in uit and "[POSTCODE]" in uit


def test_hetzelfde_via_de_reversibele_pijplijn(session):
    """Beide pijplijnen delen de detectortabel; beide moeten dit doen."""
    from wordsworth.keys import InMemoryKeyProvider
    from wordsworth.mapping_store import PostgresMappingStore
    from wordsworth.pseudonymizer import Pseudonymizer

    anon = Pseudonymizer(InMemoryKeyProvider(), PostgresMappingStore(session))
    assert "6800 GD" in anon.anonymize(POSTBUS).text
    assert "6800 GD" in anon.anonymize(MET_MAIL).text
    assert "3500 DA" not in anon.anonymize(VER_WEG).text
