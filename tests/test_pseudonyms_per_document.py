"""Een token van een ander document mag niet oplossen.

De mapping-store is globaal: opzoeken op pseudonym, niet per document. Dat is
opzet — dezelfde waarde krijgt overal hetzelfde token, en dat is wat
gepseudonimiseerde tekst doorzoekbaar maakt. De prijs is dat `_reveal` élk token
oploste dat het tegenkwam, ongeacht wie het muntte.

`neutralise_foreign_tokens` sluit de ingang die een aanvaller vandaag kan lopen.
Dit sluit de uitgang, en een uitgang is goedkoper te bewaken: er is één
reveal-pad en een onbegrensd aantal manieren waarop tekst binnenkomt.
"""
from __future__ import annotations

import uuid

from wordsworth import pseudonym_registry
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import DocumentText
from wordsworth.pipeline import get_anonymized_text, ingest, process, register
from wordsworth.pseudonymizer import Pseudonymizer, deanonymize

PII = "123456782"
PII_ANDER = "111222333"


def _pseudo(session):
    return Pseudonymizer(InMemoryKeyProvider(), PostgresMappingStore(session))


class TestRegistratie:
    def test_tokens_in_de_tekst_zijn_gevonden(self):
        t = "geen [BSN:ab12cd34] en [EMAIL:00ff11aa] hier"
        assert pseudonym_registry.tokens_in(t) == {"[BSN:ab12cd34]", "[EMAIL:00ff11aa]"}

    def test_tekst_zonder_tokens_geeft_niets(self):
        assert pseudonym_registry.tokens_in("gewone tekst") == set()
        assert pseudonym_registry.tokens_in("") == set()

    def test_iets_dat_op_een_token_lijkt_telt_niet(self):
        """Het formaat is nauw: hoofdletters, dubbele punt, acht hex."""
        for bijna in ("[bsn:ab12cd34]", "[BSN:ab12cd3]", "[BSN:ZZ12cd34]", "[BSN]"):
            assert pseudonym_registry.tokens_in(f"x {bijna} y") == set(), bijna


class TestReveal:
    def test_een_eigen_token_lost_gewoon_op(self, session, mem_store, mem_index,
                                            fake_embedder, born_digital_pii_pdf):
        kp = InMemoryKeyProvider()          # dezelfde sleutels bij anonimiseren én onthullen
        doc = ingest(session, mem_store, born_digital_pii_pdf)
        session.commit()
        process(session, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(session)),
                search_index=mem_index, embedder=fake_embedder)
        session.commit()
        tekst = get_anonymized_text(session, doc.id)
        assert pseudonym_registry.registered(session, doc.id)
        restored = deanonymize(session, doc.id, tekst, kp,
                               PostgresMappingStore(session), actor="mark")
        assert restored != tekst          # er is iets onthuld

    def test_een_token_van_een_ander_document_lost_niet_op(self, session):
        """Het lek, in het klein: een token oogsten uit een document dat je mag
        inzien en het in je eigen document zetten."""
        a, b = register(session, "a"), register(session, "b")
        session.flush()
        doc_a, doc_b = a.id, b.id
        vreemd = "[BSN:ab12cd34]"
        pseudonym_registry.register(session, doc_a, f"van A: {vreemd}")
        session.flush()
        assert vreemd in pseudonym_registry.registered(session, doc_a)
        assert vreemd not in pseudonym_registry.registered(session, doc_b)


class TestHerkomst:
    def test_een_backfill_zegt_dat_hij_dat_is(self, session):
        """Een backfill leest de opgeslagen tekst en kan niet zien of een token
        daar gemunt is of vóór de guard is binnengeslopen. Wie later een incident
        onderzoekt hoort dat verschil te zien in plaats van het aan te nemen."""
        from sqlalchemy import select

        from wordsworth.models import DocumentPseudonym
        doc = register(session, "h").id
        session.flush()
        pseudonym_registry.register(session, doc, "[BSN:ab12cd34]",
                                    source=pseudonym_registry.BACKFILLED)
        session.flush()
        rij = session.execute(
            select(DocumentPseudonym).where(DocumentPseudonym.document_id == doc)
        ).scalar_one()
        assert rij.source == "backfilled"

    def test_registreren_is_idempotent(self, session):
        doc = register(session, "i").id
        session.flush()
        assert pseudonym_registry.register(session, doc, "[BSN:ab12cd34]") == 1
        session.flush()
        assert pseudonym_registry.register(session, doc, "[BSN:ab12cd34]") == 0


def test_het_lek_end_to_end(session, mem_store, mem_index, fake_embedder,
                            born_digital_pii_pdf):
    """Twee documenten, één geoogst token.

    Dit is het scenario uit de security-review: oogst een token uit een document
    dat je mag inzien, zet het in je eigen document, vraag een grant die netjes
    op jouw document gescoped is, en onthul andermans waarde. De documentscope
    van de grant is dan betekenisloos.

    De guard maakt zo'n geplakt token al onschadelijk bij het anonimiseren. Deze
    test gaat om de laag eronder: ook als een token langs een andere weg in de
    opgeslagen tekst komt, mag hij niet oplossen.
    """
    kp = InMemoryKeyProvider()
    slachtoffer = ingest(session, mem_store, born_digital_pii_pdf)
    session.commit()
    process(session, slachtoffer.id, mem_store,
            anonymizer=Pseudonymizer(kp, PostgresMappingStore(session)),
            search_index=mem_index, embedder=fake_embedder)
    session.commit()
    geoogst = sorted(pseudonym_registry.tokens_in(
        get_anonymized_text(session, slachtoffer.id)))
    assert geoogst, "opzet klopt niet: er viel niets te oogsten"

    # Het eigen document van de aanvaller, met het geoogste token erin gezet
    # buiten de anonimisering om (dus voorbij de guard).
    aanvaller = register(session, "aanvaller")
    session.flush()
    gestolen = f"mijn document met {geoogst[0]} erin"
    session.merge(DocumentText(document_id=aanvaller.id, anonymized_text=gestolen))
    session.flush()

    restored = deanonymize(session, aanvaller.id, gestolen, kp,
                           PostgresMappingStore(session), actor="aanvaller")
    assert restored == gestolen, "andermans token loste alsnog op"
    assert geoogst[0] in restored          # het token blijft staan, stil


def test_backfill_registreert_bestaande_documenten(session, mem_store, mem_index,
                                                   fake_embedder, born_digital_pii_pdf):
    """Zonder backfill onthult elk bestaand document niets meer.

    Dat is fail-closed en dus het juiste gedrag, maar het verkeerde om in
    productie te ontdekken. De backfill hoort bij de uitrol, niet erna.
    """
    from sqlalchemy import delete, select

    from wordsworth.models import DocumentPseudonym

    kp = InMemoryKeyProvider()
    doc = ingest(session, mem_store, born_digital_pii_pdf)
    session.commit()
    process(session, doc.id, mem_store,
            anonymizer=Pseudonymizer(kp, PostgresMappingStore(session)),
            search_index=mem_index, embedder=fake_embedder)
    session.commit()

    # Doe alsof dit document van vóór de change is: gooi de registratie weg.
    session.execute(delete(DocumentPseudonym).where(
        DocumentPseudonym.document_id == doc.id))
    session.flush()
    tekst = get_anonymized_text(session, doc.id)
    assert pseudonym_registry.registered(session, doc.id) == set()
    assert deanonymize(session, doc.id, tekst, kp, PostgresMappingStore(session),
                       actor="x") == tekst          # onthult niets meer

    # De backfill leest de opgeslagen tekst en herstelt de koppeling.
    n = pseudonym_registry.register(session, doc.id, tekst,
                                    source=pseudonym_registry.BACKFILLED)
    session.flush()
    assert n > 0
    assert deanonymize(session, doc.id, tekst, kp, PostgresMappingStore(session),
                       actor="x") != tekst          # en onthult weer

    herkomst = {r.source for r in session.execute(
        select(DocumentPseudonym).where(DocumentPseudonym.document_id == doc.id)
    ).scalars()}
    assert herkomst == {"backfilled"}
