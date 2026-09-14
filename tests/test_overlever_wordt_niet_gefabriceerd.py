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

import pytest

from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.openanonymiser_driver import (
    AnonymizationInvariantError,
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


def test_de_sentinel_verwijdert_het_token_maar_plakt_niets_aan_elkaar():
    """De twee eisen aan het strippen, allebei vastgelegd.

    Strippen bestaat omdat een ingevoegd token zelf geen gedetecteerde waarde
    mag matchen — die eis blijft. Wat eraan ontbrak is de tweede: het weghalen
    mag de tekst links en rechts niet aan elkaar plakken, want dan ontstaat een
    woordgrens die er niet was.
    """
    import re

    from wordsworth.pseudonymizer import _PSEUDONYM_RE

    tekst = "J. [PERSON:ab12cd34] B"
    gestript = _PSEUDONYM_RE.sub("\x00", tekst)

    assert "PERSON" not in gestript          # het token is weg
    assert "ab12cd34" not in gestript
    # en "J." en "B" zijn niet buren geworden:
    assert re.search(r"(?<!\w)J\.\s+B(?!\w)", gestript) is None
    assert re.search(r"(?<!\w)J\.\s+B(?!\w)", _PSEUDONYM_RE.sub("", tekst))
