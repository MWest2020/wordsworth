# SPDX-License-Identifier: MIT
"""Wat een dossierwijziging achterlaat, en waar (dossier-audit).

Tot deze change liet het verplaatsen van een document geen enkel spoor na: de
securityreview greptte op `audit` over `dossiers.py`, `dossier_tools.py` en
`backfill_dossier.py` en vond nul treffers. Je zag achteraf de uitkomst en niet
de handeling, terwijl de vraag die een maand later gesteld wordt precies is
"wie heeft dit verplaatst, en wanneer".

Deze toetsen pinnen de scheiding vast die dat oplost, want die scheiding is de
hele beslissing: een LIDMAATSCHAP hoort op de hashketen van dat ene document, een
HERNOEMING hoort in de sleutel-levensloopstroom omdat hij geen document verplaatst.
"""
from sqlalchemy import select

import pytest

from wordsworth import dossier_events, dossiers
from wordsworth.models import AuditRecord
from wordsworth.pipeline import register


def _records(session, document_id, step):
    return [r for r in session.execute(
        select(AuditRecord).where(AuditRecord.document_id == document_id)
        .order_by(AuditRecord.seq)).scalars() if r.step == step]


class TestLidmaatschap:
    def test_toevoegen_schrijft_een_record_op_het_document(self, session):
        d = dossiers.ensure(session, "zaak-a")
        doc = register(session, "documents/spoor-1")
        session.commit()
        dossiers.add(session, d.id, doc.id, actor="mark@westerweel.work")

        recs = _records(session, doc.id, dossier_events.ADDED)
        assert len(recs) == 1
        assert recs[0].payload["dossier"] == "zaak-a"
        assert recs[0].payload["actor"] == "mark@westerweel.work"

    def test_het_is_een_gebeurtenis_en_geen_toestandsovergang(self, session):
        """from == to. Een document dat in een andere zaak belandt, staat in
        precies dezelfde staat als daarvoor; een overgang claimen zou
        `current_state` laten liegen."""
        d = dossiers.ensure(session, "zaak-b")
        doc = register(session, "documents/spoor-2")
        session.commit()
        dossiers.add(session, d.id, doc.id, actor="test")

        rec = _records(session, doc.id, dossier_events.ADDED)[0]
        assert rec.from_state == rec.to_state

    def test_een_verwijdering_zonder_reden_wordt_geweigerd(self, session):
        """De asymmetrie is de hele afspraak: een toevoeging is terug te zien in
        het resultaat, een verwijdering laat niets achter behalve wat iemand
        toen opschreef."""
        d = dossiers.ensure(session, "zaak-c")
        doc = register(session, "documents/spoor-3")
        session.commit()
        dossiers.add(session, d.id, doc.id, actor="test")

        with pytest.raises(dossiers.DossierError, match="reason"):
            dossiers.remove(session, d.id, doc.id, actor="test", reason="   ")
        # en het lidmaatschap staat er nog: geweigerd is niet half uitgevoerd
        assert dossiers.documents_in(session, [d.id]) == {doc.id}

    def test_een_verwijdering_bewaart_de_reden_en_de_dossiernaam(self, session):
        d = dossiers.ensure(session, "zaak-d")
        doc = register(session, "documents/spoor-4")
        session.commit()
        dossiers.add(session, d.id, doc.id, actor="test")
        dossiers.remove(session, d.id, doc.id, actor="mark", reason="verkeerd ingedeeld")

        rec = _records(session, doc.id, dossier_events.REMOVED)[0]
        assert rec.payload["reason"] == "verkeerd ingedeeld"
        assert rec.payload["dossier"] == "zaak-d"   # gelezen vóór het verwijderen

    def test_een_lidmaatschap_dat_er_al_was_schrijft_niets(self, session):
        """Anders telt een herhaalde ingest als een handeling die niet gebeurd
        is, en dan is het spoor niet meer te vertrouwen als telling."""
        d = dossiers.ensure(session, "zaak-e")
        doc = register(session, "documents/spoor-5")
        session.commit()
        dossiers.add(session, d.id, doc.id, actor="test")
        dossiers.add(session, d.id, doc.id, actor="test")

        assert len(_records(session, doc.id, dossier_events.ADDED)) == 1

    def test_een_batch_bindt_de_records_van_een_handeling(self, session):
        """791 documenten in één commando zijn eerlijk als 791 records, en
        onleesbaar zonder iets dat zegt dat het één handeling was."""
        d = dossiers.ensure(session, "zaak-f")
        docs = [register(session, f"documents/batch-{i}") for i in range(3)]
        session.commit()
        for doc in docs:
            dossiers.add(session, d.id, doc.id, actor="backfill", batch="abc123")

        batches = {_records(session, doc.id, dossier_events.ADDED)[0].payload["batch"]
                   for doc in docs}
        assert batches == {"abc123"}


class TestHernoemen:
    def test_hernoemen_raakt_geen_enkele_documentketen(self, session):
        """De kern van de beslissing. Een hernoeming verplaatst geen document,
        dus duizend identieke records zouden de keten volschrijven met kopieën
        van één feit."""
        d = dossiers.ensure(session, "oude-naam")
        doc = register(session, "documents/hernoem-1")
        session.commit()
        dossiers.add(session, d.id, doc.id, actor="test")
        voor = len(list(session.execute(
            select(AuditRecord).where(AuditRecord.document_id == doc.id)).scalars()))

        dossiers.rename(session, "oude-naam", "nieuwe-naam", actor="mark")

        na = len(list(session.execute(
            select(AuditRecord).where(AuditRecord.document_id == doc.id)).scalars()))
        assert na == voor

    def test_hernoemen_landt_in_de_sleutel_levensloopstroom(self, session):
        d = dossiers.ensure(session, "oud")
        docs = [register(session, f"documents/hernoem-{i}") for i in range(2)]
        session.commit()
        for doc in docs:
            dossiers.add(session, d.id, doc.id, actor="test")

        gezien = {}

        class NepStroom:
            def dossier_renamed(self, **kw):
                gezien.update(kw)

        dossiers.rename(session, "oud", "nieuw", actor="mark", lifecycle=NepStroom())

        assert gezien["old"] == "oud" and gezien["new"] == "nieuw"
        assert gezien["actor"] == "mark"
        # Hoe ver de wijziging reikte -- het getal waarvoor dit record bestaat.
        assert gezien["documents"] == 2

    def test_zonder_stroom_hernoemt_hij_gewoon(self, session):
        """`lifecycle=None` is de testmodus en de bestaande conventie van de
        audit-naad; het mag geen hernoeming tegenhouden."""
        dossiers.ensure(session, "a")
        session.commit()
        assert dossiers.rename(session, "a", "b", actor="test").name == "b"
