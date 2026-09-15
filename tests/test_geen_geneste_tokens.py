"""Een token mag nooit in een ander token terechtkomen (DB-backed).

Gemeten op 2026-09-14: 266 geneste tokens in 150 van de 770 documenten, zoals
`[POSTCODE:[EMAIL:52a0d245]]`. De deterministische laag maakt
`[POSTCODE:007f03af]`; daarna ziet GLiNER in díé tekst iets wat op een
e-mailadres lijkt en vervangt het.

Er lekt niets — er staat nog steeds geen klare PII. Maar het POSTCODE-token is
kapot: de pseudoniem-string komt niet meer overeen met de sleutel in de mapping,
dus die waarde is niet meer te onthullen. Stil dataverlies, en onthulbaarheid is
de hele belofte van de reversibele kant.
"""
from __future__ import annotations

import re

from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.openanonymiser_driver import Entity
from wordsworth.pseudonymizer import ReversibleAnonymizer

GENEST = re.compile(r"\[[A-Z0-9_]+:\[")
TOKEN = re.compile(r"\[[A-Z0-9_]+:[0-9a-f]{8}\]")


def test_de_entiteitslaag_blijft_van_bestaande_tokens_af(session):
    """GLiNER geeft een waarde terug die binnen een al geplaatst token valt."""
    tekst = "Aanslagnummer 123456782 en verder niets bijzonders."

    gezien: dict[str, str] = {}

    def detect(t: str) -> list[Entity]:
        # Precies het gemeten geval: de hash van het BSN-token wordt als
        # entiteit teruggegeven. Hij staat tussen ":" en "]", dus tussen twee
        # niet-woordtekens — de grenscontrole slaat wél aan.
        m = TOKEN.search(t)
        if not m:
            return []
        hash_deel = m.group(0).split(":")[1].rstrip("]")
        gezien["hash"] = hash_deel
        return [Entity(entity_type="EMAIL", text=hash_deel, start=0, end=0)]

    anon = ReversibleAnonymizer(InMemoryKeyProvider(),
                                PostgresMappingStore(session), detect=detect)
    uit = anon.anonymize(tekst).text

    assert gezien.get("hash"), "de opzet klopt niet: er was geen token om in te grijpen"
    assert GENEST.search(uit) is None, f"genest token gemaakt: {uit!r}"
    assert "123456782" not in uit                 # het BSN is nog steeds weg


def test_een_gewone_waarde_buiten_een_token_wordt_nog_wel_vervangen(session):
    """Geen versoepeling: alleen bínnen een token blijft de laag eraf."""
    tekst = "Aanslagnummer 123456782, behandeld door Jansen."

    def detect(_t):
        return [Entity(entity_type="PERSON", text="Jansen", start=0, end=0)]

    anon = ReversibleAnonymizer(InMemoryKeyProvider(),
                                PostgresMappingStore(session), detect=detect)
    uit = anon.anonymize(tekst).text
    assert "Jansen" not in uit and "[PERSON:" in uit
    assert GENEST.search(uit) is None
