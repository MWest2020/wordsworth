"""De overlever-controle mag zijn eigen bewijs niet maken (DB-backed).

Ná de vervanging strippen we de ingevoegde tokens en controleren dat geen
gedetecteerde waarde de tekst heeft overleefd. Dat strippen ging naar niets, en
weghalen naar niets plakt de tekst links en rechts aan elkaar — waardoor een
woordgrens ontstaat die in het origineel niet bestond.

Gemeten op 2026-09-14 op acht documenten die hierdoor werden geweigerd: vijf
overlevers hadden `in_bron: 0`. De waarde stónd niet in de brontekst en
verscheen pas ná de vervanging. Er lekte niets — de controle staat aan de
veilige kant — maar hij weigerde op een onwaarheid, en dat kostte acht
documenten uit het corpus.

Dat dit kan, komt doordat een entiteitswaarde van de dienst komt (`e.text`) en
dus niet per se woord-begrensd in de tekst voorkomt.
"""
from __future__ import annotations


from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.openanonymiser_driver import (
    Entity,
)
from wordsworth.pseudonymizer import ReversibleAnonymizer

BRON = "T.a.v. J. Jansen B, afdeling vergunningen"
# "Jansen" wordt vervangen; het token wordt gestript. Ging dat naar niets, dan
# werd "J. " en " B" aan elkaar geplakt tot "J.  B" — een string die in BRON
# nergens staat, maar die de dienst wél als entiteit teruggaf.
GEFABRICEERD = "J.  B"


def _detect(_text: str) -> list[Entity]:
    return [
        Entity(entity_type="PERSON", text="Jansen",
               start=BRON.index("Jansen"), end=BRON.index("Jansen") + 6),
        Entity(entity_type="PERSON", text=GEFABRICEERD, start=0, end=0),
    ]


def _anon(session):
    return ReversibleAnonymizer(InMemoryKeyProvider(),
                               PostgresMappingStore(session), detect=_detect)


def test_de_gefabriceerde_waarde_staat_niet_in_de_bron():
    """Het uitgangspunt, expliciet: zonder dit bewijst de test niets."""
    import re
    grens = r"(?<!\w)" + re.escape(GEFABRICEERD) + r"(?!\w)"
    assert re.search(grens, BRON) is None


def test_een_gefabriceerde_overlever_blokkeert_het_document_niet(session):
    resultaat = _anon(session).anonymize(BRON)
    assert "Jansen" not in resultaat.text          # de echte waarde is weg
    assert "[PERSON:" in resultaat.text            # en vervangen door een token


def test_de_dienst_mag_spatie_eromheen_geven(session):
    """Een span komt binnen met toevallige spatiëring; dat mag niets uitmaken.

    De dienst gaf "Naarden " mét spatie terug. Op die letterlijke vorm matchen
    mist het woord — er komt een woordteken achteraan, dus de grenscontrole
    slaat niet aan — en dan blijft "Naarden" leesbaar in de uitvoer terwijl de
    fail-hard-controle het hele document verwerpt. Twee keer fout in één keer.
    """
    tekst = "gemeente Naarden Jansen."

    def detect_met_spatie(_t):
        return [Entity(entity_type="LOCATION", text="Naarden ", start=0, end=0),
                Entity(entity_type="PERSON", text="Jansen", start=0, end=0)]

    anon = ReversibleAnonymizer(InMemoryKeyProvider(),
                                PostgresMappingStore(session),
                                detect=detect_met_spatie)
    uit = anon.anonymize(tekst).text
    assert "Naarden" not in uit and "Jansen" not in uit
    assert uit.count("[LOCATION:") == 1 and uit.count("[PERSON:") == 1


def test_het_masker_houdt_dezelfde_woordgrenzen_als_de_waarde():
    """Een token vervangen door iets met dezelfde woord-eigenschap aan beide
    kanten, zodat de controle dezelfde grenzen ziet als de vervanging.

    Naar niets strippen plakt de tekst aan elkaar; naar een vast niet-woordteken
    strippen maakt een grens waar een woordteken stond. Allebei fout, in
    tegengestelde richting.
    """
    import re

    from wordsworth.pseudonymizer import _PSEUDONYM_RE

    # "Jansen" begint en eindigt met een woordteken, dus het masker ook.
    tekst = "voorJansenna"
    met_token = "voor[PERSON:ab12cd34]na"

    naar_niets = _PSEUDONYM_RE.sub("", met_token)          # "voorna"
    naar_sentinel = _PSEUDONYM_RE.sub("\x00", met_token)   # "voor\x00na"
    naar_masker = _PSEUDONYM_RE.sub("xx", met_token)       # "voorxxna"

    # "voor" stond midden in een woord en hoort dat te blijven.
    grens = r"(?<!\w)voor(?!\w)"
    assert re.search(grens, tekst) is None                 # in de bron: geen grens
    assert re.search(grens, naar_niets) is None            # toevallig ook niet
    assert re.search(grens, naar_sentinel) is not None     # FOUT: grens gemaakt
    assert re.search(grens, naar_masker) is None           # goed: grens behouden


def test_een_waarde_middenin_een_woord_geeft_geen_vals_alarm(session):
    """Het geval van de drie documenten, in het klein.

    De waarde staat woord-begrensd in de tekst én een keer middenin een woord.
    De begrensde voorkomens worden vervangen; het voorkomen middenin blijft
    staan, want dat vervangen zou gewone tekst mangelen. Dat mag geen alarm zijn.
    """
    tekst = "B.V staat hier, en ook in aB.Vc verstopt."

    def detect(_t):
        return [Entity(entity_type="ORGANIZATION", text="B.V", start=0, end=3)]

    anon = ReversibleAnonymizer(InMemoryKeyProvider(),
                                PostgresMappingStore(session), detect=detect)
    uit = anon.anonymize(tekst).text
    assert uit.startswith("[ORGANIZATION:")     # het begrensde voorkomen is weg
    assert "aB.Vc" in uit                       # het ingebedde is met rust gelaten
