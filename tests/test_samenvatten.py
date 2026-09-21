# SPDX-License-Identifier: MIT
"""Het commando `python -m wordsworth.samenvatten` (samenvatten-als-commando).

Geen Ollama nodig: een nep-generator zoals in `test_summaries.py`. De
rekenkern (`compute`) heeft daar al zijn eigen tests; hier gaat het om de
invoer (--dossier / --ontbrekend / niets), de uitvoer (één regel, vijf
tellingen) en de exitcode.
"""
from __future__ import annotations

import pytest

from wordsworth import samenvatten
from wordsworth.dossiers import add, ensure
from wordsworth.generator import GenerationError
from wordsworth.models import Document, DocumentText


class _Keep:
    """Een sessie die `with` overleeft, zodat het commando de sessie van de
    test gebruikt in plaats van er zelf een op te zetten."""

    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *a):
        return False


class Model:
    def __init__(self, tekst="Het besluit gaat over een dakkapel."):
        self.tekst, self.aanroepen = tekst, []

    def generate(self, query, sources):        # pragma: no cover - niet gebruikt
        raise AssertionError("summarise, niet generate")

    def summarise(self, text: str) -> str:
        self.aanroepen.append(text)
        return self.tekst


def _doc(session, tekst="De aanvraag voor een dakkapel is afgewezen."):
    doc = Document(object_key=f"documents/{id(tekst)}-{len(tekst or '')}")
    session.add(doc)
    session.flush()
    if tekst is not None:
        session.merge(DocumentText(document_id=doc.id, anonymized_text=tekst))
    session.flush()
    return doc


def _wire(monkeypatch, session, generator):
    """Zet het commando op de sessie en generator van de test, net als
    `test_a_dry_run_does_not_touch_the_index` dat doet voor `backfill_dossier`."""
    monkeypatch.setattr(samenvatten, "make_engine", lambda: None)
    monkeypatch.setattr(samenvatten, "make_session_factory",
                        lambda e: (lambda: _Keep(session)))
    monkeypatch.setattr(samenvatten.OllamaGenerator, "from_config",
                        classmethod(lambda cls: generator))


def test_without_arguments_it_explains_and_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        samenvatten.main([])
    assert exc.value.code == 2
    assert "dossier" in capsys.readouterr().err.lower()


def test_it_reports_one_line_with_the_five_counts_and_the_duration(
        session, monkeypatch, capsys):
    d = ensure(session, "zaak-samenvatten")
    session.flush()
    doc = _doc(session)
    add(session, d.id, doc.id)
    session.commit()
    model = Model()
    _wire(monkeypatch, session, model)

    code = samenvatten.main(["--dossier", str(d.id)])

    assert code == 0
    uit = capsys.readouterr().out
    for veld in ("seen=1", "made=1", "skipped=0", "failed=0",
                "without_text=0", "duur="):
        assert veld in uit, uit
    assert model.aanroepen == ["De aanvraag voor een dakkapel is afgewezen."]


def test_running_again_does_not_call_the_generator_again(
        session, monkeypatch, capsys):
    """De spec-eis: een tweede run maakt niets opnieuw, en roept de generator
    dus niet aan voor een document dat al een samenvatting heeft."""
    d = ensure(session, "zaak-nogmaals")
    session.flush()
    doc = _doc(session)
    add(session, d.id, doc.id)
    session.commit()
    model = Model()
    _wire(monkeypatch, session, model)

    eerste = samenvatten.main(["--dossier", str(d.id)])
    tweede = samenvatten.main(["--dossier", str(d.id)])

    assert (eerste, tweede) == (0, 0)
    assert len(model.aanroepen) == 1, "de generator is twee keer aangeroepen"
    assert "skipped=1" in capsys.readouterr().out


def test_a_failed_document_gives_a_nonzero_exit_code(session, monkeypatch, capsys):
    class Kapot:
        def generate(self, query, sources):     # pragma: no cover
            raise AssertionError

        def summarise(self, text: str) -> str:
            raise GenerationError("ollama weg")

    d = ensure(session, "zaak-mislukt")
    session.flush()
    doc = _doc(session)
    add(session, d.id, doc.id)
    session.commit()
    _wire(monkeypatch, session, Kapot())

    code = samenvatten.main(["--dossier", str(d.id)])

    assert code == 1
    assert "failed=1" in capsys.readouterr().out


def test_a_document_without_text_gives_a_nonzero_exit_code_too(
        session, monkeypatch, capsys):
    """De spec-scenario: één document zonder tekst, de rest wel -- de overige
    samenvattingen worden gemaakt, en de exitcode is ongelijk aan nul."""
    d = ensure(session, "zaak-zonder-tekst")
    session.flush()
    met_tekst = _doc(session)
    zonder_tekst = _doc(session, None)
    add(session, d.id, met_tekst.id)
    add(session, d.id, zonder_tekst.id)
    session.commit()
    model = Model()
    _wire(monkeypatch, session, model)

    code = samenvatten.main(["--dossier", str(d.id)])

    assert code == 1
    uit = capsys.readouterr().out
    assert "made=1" in uit and "without_text=1" in uit


def test_ontbrekend_finds_every_document_without_a_summary(
        session, monkeypatch, capsys):
    """`--ontbrekend`: niet gescoped op een dossier, maar letterlijk alles wat
    nog geen samenvatting heeft."""
    d = ensure(session, "zaak-ontbrekend")
    session.flush()
    heeft_nog_niets = _doc(session, "Een besluit over een hek.")
    add(session, d.id, heeft_nog_niets.id)
    session.commit()
    model = Model("Het gaat over een hek.")
    _wire(monkeypatch, session, model)

    code = samenvatten.main(["--ontbrekend"])

    assert code == 0
    assert "seen=1" in capsys.readouterr().out
    assert model.aanroepen == ["Een besluit over een hek."]


def test_dossier_and_ontbrekend_together_is_rejected(capsys):
    with pytest.raises(SystemExit) as exc:
        samenvatten.main(["--dossier", "00000000-0000-0000-0000-000000000000",
                          "--ontbrekend"])
    assert exc.value.code == 2
