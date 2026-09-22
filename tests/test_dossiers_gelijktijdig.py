# SPDX-License-Identifier: MIT
"""Twee schrijvers tegelijk op hetzelfde dossier (codereview 18-09).

`ensure` en `add` lazen eerst en schreven dan, met een unieke sleutel eronder.
De review mat het: verzoek B blokkeerde drie seconden op de unieke index en
kreeg toen een onafgevangen IntegrityError — en in `_ingest_one` omspant die
transactie de hele straat voor een document, dus dat wachten duurt zo lang als
de ander erover doet.

Getoetst tegen een echte Postgres met twee sessies. Een testdubbel bewijst hier
niets: wat hier faalt is de database, niet de code.
"""
from sqlalchemy import select

from wordsworth import dossiers
from wordsworth.models import Dossier
from wordsworth.pipeline import register


def test_two_sessions_creating_the_same_dossier_at_the_same_time(session_factory):
    """Het échte geval: beide sessies kijken vóórdat een van de twee commit,
    dus beide zien niets en beide schrijven. Zonder draad is dit geen race maar
    een volgorde, en dan toetst de test niets."""
    import threading

    begonnen = threading.Event()
    klaar = threading.Event()
    uitkomst = {}

    def tweede_schrijver():
        s = session_factory()
        try:
            begonnen.wait(5)
            # Blokkeert op de unieke index tot A commit; daarna botst het insert
            # en vangt het savepoint dat op.
            uitkomst["id"] = dossiers.ensure(s, "zelfde zaak").id
            s.commit()
        except Exception as exc:          # pragma: no cover - dit is de bug
            uitkomst["fout"] = f"{type(exc).__name__}: {exc}"
            s.rollback()
        finally:
            s.close()
            klaar.set()

    a = session_factory()
    try:
        eerste = dossiers.ensure(a, "zelfde zaak")   # insert, nog niet gecommit
        draad = threading.Thread(target=tweede_schrijver)
        draad.start()
        begonnen.set()
        import time
        time.sleep(0.3)                  # B zit nu te wachten op de index
        a.commit()                       # A wint
        klaar.wait(10)
        draad.join(5)
    finally:
        a.close()

    assert "fout" not in uitkomst, uitkomst["fout"]
    assert uitkomst["id"] == eerste.id, "B hoort A's dossier te krijgen"
    with session_factory() as s:
        assert len(s.execute(select(Dossier)).scalars().all()) == 1


def test_a_losing_writer_keeps_its_own_work(session_factory):
    """Het savepoint is er niet om de botsing te overleven maar om de rest van
    de sessie te redden: die draagt het halve werk van een document."""
    a, b = session_factory(), session_factory()
    try:
        doc = register(b, "documents/aa", filename="a.pdf")   # B's eigen werk
        b.flush()
        dossiers.ensure(a, "zaak")
        a.commit()
        gedeeld = dossiers.ensure(b, "zaak")                  # B verliest de race
        dossiers.add(b, gedeeld.id, doc.id, actor="test")
        b.commit()
        with session_factory() as s:
            assert s.get(Dossier, gedeeld.id) is not None
            from wordsworth.pipeline import dossiers_of
            assert dossiers_of(s, doc.id) == [str(gedeeld.id)]
    finally:
        a.close(); b.close()


def test_adding_the_same_membership_from_two_sessions_is_not_an_error(session_factory):
    a, b = session_factory(), session_factory()
    try:
        d = dossiers.ensure(a, "zaak")
        doc = register(a, "documents/aa")
        a.commit()
        assert dossiers.add(a, d.id, doc.id, actor="test") is True
        a.commit()
        assert dossiers.add(b, d.id, doc.id, actor="test") is False
        b.commit()
    finally:
        a.close(); b.close()
