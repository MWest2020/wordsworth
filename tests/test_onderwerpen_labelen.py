# SPDX-License-Identifier: MIT
"""Het commando `python -m wordsworth.onderwerpen_labelen` (topic-labels-llm).

Geen Ollama en geen OpenSearch: het commando krijgt de sessie, een
`InMemoryIndex` en een nep-generator van de test, zoals `test_samenvatten.py`
dat doet. Getoetst: de regel uitvoer, de exitcode, en dat een tweede run het
werk niet overdoet.
"""
from __future__ import annotations

import pytest

from topic_label_setup import Kapot, Keep, Model, dossier
from wordsworth import onderwerpen_labelen as cmd
from wordsworth.models import Topic
from wordsworth.search_index import InMemoryIndex, SearchUnavailable


def _wire(monkeypatch, session, index, generator):
    monkeypatch.setattr(cmd, "make_engine", lambda: None)
    monkeypatch.setattr(cmd, "make_session_factory",
                        lambda e: (lambda: Keep(session)))
    monkeypatch.setattr(cmd.OllamaGenerator, "from_config",
                        classmethod(lambda cls: generator))
    monkeypatch.setattr(cmd, "_index", lambda: index)


def _drie(session, index, naam="zaak-cmd"):
    return dossier(session, index, naam=naam, topics=[
        (f"term{n} · ander{n}", [([float(n), 1.0], f"samenvatting {n}")] * 2)
        for n in range(3)])


def test_without_a_dossier_it_explains_and_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        cmd.main([])
    assert exc.value.code == 2
    assert "--dossier" in capsys.readouterr().err


def test_it_labels_the_dossier_and_reports_one_line(session, monkeypatch, capsys):
    index = InMemoryIndex()
    _, topics, _ = _drie(session, index)
    model = Model()
    _wire(monkeypatch, session, index, model)

    assert cmd.main(["--dossier", "zaak-cmd"]) == 0

    uit = capsys.readouterr().out.strip()
    assert len(uit.splitlines()) == 1
    for veld in ("seen=3", "labelled=3", "rejected=0", "no_summaries=0",
                "skipped=0", "failed=0", "model=nep-model", "duur="):
        assert veld in uit, uit
    session.expire_all()
    assert all(session.get(Topic, t.id).llm_label for t in topics)


def test_a_second_run_does_not_call_the_model(session, monkeypatch, capsys):
    index = InMemoryIndex()
    _drie(session, index)
    model = Model()
    _wire(monkeypatch, session, index, model)

    eerste = cmd.main(["--dossier", "zaak-cmd"])
    tweede = cmd.main(["--dossier", "zaak-cmd"])

    assert (eerste, tweede) == (0, 0)
    assert len(model.prompts) == 3, "de tweede run riep het model opnieuw aan"
    assert "skipped=3" in capsys.readouterr().out.splitlines()[-1]


def test_opnieuw_labels_every_topic_again(session, monkeypatch, capsys):
    index = InMemoryIndex()
    _drie(session, index)
    model = Model()
    _wire(monkeypatch, session, index, model)

    cmd.main(["--dossier", "zaak-cmd"])
    assert cmd.main(["--dossier", "zaak-cmd", "--opnieuw"]) == 0

    assert len(model.prompts) == 6
    assert "labelled=3" in capsys.readouterr().out.splitlines()[-1]


def test_a_failed_model_call_gives_a_nonzero_exit_code(session, monkeypatch, capsys):
    index = InMemoryIndex()
    _drie(session, index)
    _wire(monkeypatch, session, index, Kapot(bij=2))

    assert cmd.main(["--dossier", "zaak-cmd"]) == 1
    uit = capsys.readouterr().out
    assert "labelled=2" in uit and "failed=1" in uit


def test_a_rejected_label_alone_exits_zero_and_is_counted(session, monkeypatch,
                                                         capsys):
    index = InMemoryIndex()
    _drie(session, index)
    _wire(monkeypatch, session, index,
          Model({"label": "[PERSOON] en bomen", "description": "Goed."}))

    assert cmd.main(["--dossier", "zaak-cmd"]) == 0
    assert "rejected=3" in capsys.readouterr().out


def test_an_unreachable_index_exits_nonzero_and_labels_nothing(session, monkeypatch,
                                                               capsys):
    class Weg(InMemoryIndex):
        def documents_in(self, dossier, limit=10000):
            raise SearchUnavailable("index weg")

    _, topics, _ = _drie(session, InMemoryIndex())
    model = Model()
    _wire(monkeypatch, session, Weg(), model)

    assert cmd.main(["--dossier", "zaak-cmd"]) == 1
    assert "zoekindex is onbereikbaar" in capsys.readouterr().err
    assert model.prompts == []
    session.expire_all()
    assert not any(session.get(Topic, t.id).llm_label for t in topics)


def test_an_unknown_dossier_exits_nonzero(session, monkeypatch, capsys):
    model = Model()
    _wire(monkeypatch, session, InMemoryIndex(), model)

    assert cmd.main(["--dossier", "bestaat-niet"]) == 1
    assert "bestaat niet" in capsys.readouterr().err
    assert model.prompts == []
