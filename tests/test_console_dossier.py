# SPDX-License-Identifier: MIT
"""The console starts on a dossier (console-dossier-home)."""
from pathlib import Path

from fastapi.testclient import TestClient

from wordsworth import dossiers
from wordsworth.api import create_app
from wordsworth.deletion import delete_document
from wordsworth.models import Document, DocumentText, Topic
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import register, transition
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

KEYS = {"s3cret": "mark"}
SRC = Path(__file__).parent.parent / "src" / "wordsworth"


def _client(session_factory):
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   follow_redirects=False, base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    return c


def _doc(session, dossier, name):
    d = register(session, f"documents/{name}", filename=name)
    session.merge(DocumentText(document_id=d.id, anonymized_text="tekst"))
    if dossier is not None:
        dossiers.add(session, dossiers.ensure(session, dossier).id, d.id,
                     actor="test")
    session.flush()
    return d


def _supersede(session, copy_id, survivor_id):
    """As in test_console.py: the state and the column, without the
    same-object-key rule of the supersession workflow."""
    transition(session, copy_id, State.SUPERSEDED, step="supersede",
               payload={"superseded_by": str(survivor_id), "actor": "test"})
    session.get(Document, copy_id).superseded_by = survivor_id


def test_without_dossiers_the_home_says_so_and_links_the_full_list(
        session_factory):
    with session_factory() as s:
        _doc(s, None, "los.pdf")
        s.commit()
    r = _client(session_factory).get("/console")
    assert r.status_code == 200
    assert "nog geen dossiers" in r.text
    assert 'href="/console/documents"' in r.text
    assert "los.pdf" not in r.text


def test_one_dossier_opens_directly(session_factory):
    with session_factory() as s:
        _doc(s, "Gooise Meren 2022", "a.pdf")
        s.commit()
    c = _client(session_factory)
    r = c.get("/console")
    assert r.status_code == 303
    assert r.headers["location"] == "/console/dossier?dossier=Gooise%20Meren%202022"
    page = c.get(r.headers["location"])
    assert page.status_code == 200 and "a.pdf" in page.text


def test_two_dossiers_show_the_picker_with_live_documents_and_topics(
        session_factory):
    with session_factory() as s:
        _doc(s, "een", "1.pdf")
        gone = _doc(s, "een", "2.pdf")
        _doc(s, "twee", "3.pdf")
        s.add(Topic(dossier_id=dossiers.ensure(s, "twee").id,
                    computed_name="vergunning", document_count=1))
        delete_document(s, gone.id, InMemoryObjectStore(), InMemoryIndex(),
                        actor="test")
        s.commit()
    r = _client(session_factory).get("/console")
    assert r.status_code == 200
    rows = r.text.split("<tbody>")[1]
    een, twee = rows.split("</tr>")[1], rows.split("</tr>")[0]
    # newest first; "een" counts 1 live document, not the deleted one
    assert "twee" in twee and "<td>1</td>\n  <td>1</td>" in twee
    assert "een" in een and "<td>1</td>\n  <td>0</td>" in een
    assert 'href="/console/dossier?dossier=een"' in r.text


def test_the_dossier_page_shows_question_box_topics_and_live_documents_only(
        session_factory):
    with session_factory() as s:
        live = _doc(s, "d", "levend.pdf")
        gone = _doc(s, "d", "weg.pdf")
        copy = _doc(s, "d", "kopie.pdf")
        _doc(s, "ander", "elders.pdf")
        delete_document(s, gone.id, InMemoryObjectStore(), InMemoryIndex(),
                        actor="test")
        _supersede(s, copy.id, live.id)
        topic = Topic(dossier_id=dossiers.ensure(s, "d").id,
                      computed_name="bouwvergunning", given_name="Bouwen",
                      document_count=1)
        s.add(topic)
        s.commit()
        topic_id = topic.id
    c = _client(session_factory)
    page = c.get("/console/dossier", params={"dossier": "d"})
    assert page.status_code == 200
    t = page.text
    assert "levend.pdf" in t
    for absent in ("weg.pdf", "kopie.pdf", "elders.pdf"):
        assert absent not in t, absent
    assert 'action="/console/search"' in t
    assert '<input type="hidden" name="dossier" value="d">' in t
    assert f'href="/console/search?dossier=d&amp;topic={topic_id}"' in t
    assert "Bouwen" in t                       # the given name wins
    assert "2 verwijderd of vervangen documenten verborgen" in t
    assert 'href="/console/dossier?dossier=d&amp;alles=1"' in t

    shown = c.get("/console/dossier", params={"dossier": "d", "alles": "1"})
    assert "weg.pdf" in shown.text and "kopie.pdf" in shown.text
    assert "elders.pdf" not in shown.text
    assert 'href="/console/dossier?dossier=d">Verberg ze weer' in shown.text


def test_the_page_says_how_much_of_the_dossier_the_topics_cover(
        session_factory):
    with session_factory() as s:
        for n in range(3):
            _doc(s, "d", f"{n}.pdf")
        d = dossiers.ensure(s, "d")
        s.add_all([Topic(dossier_id=d.id, computed_name="a", document_count=1),
                   Topic(dossier_id=d.id, computed_name="b", document_count=1)])
        s.commit()
    page = _client(session_factory).get("/console/dossier?dossier=d").text
    assert "2 van 3\n documenten vallen in een onderwerp" in page


def test_without_topics_the_page_says_so(session_factory):
    with session_factory() as s:
        _doc(s, "d", "a.pdf")
        s.commit()
    page = _client(session_factory).get("/console/dossier?dossier=d").text
    assert "Nog geen onderwerpen berekend" in page
    assert "vallen in een onderwerp" not in page


def test_names_with_a_slash_and_a_space_resolve_to_their_own_page(
        session_factory):
    with session_factory() as s:
        _doc(s, "a/b", "slash.pdf")
        _doc(s, "a b", "space.pdf")
        s.commit()
    c = _client(session_factory)
    home = c.get("/console").text
    assert 'href="/console/dossier?dossier=a%2Fb"' in home
    assert 'href="/console/dossier?dossier=a%20b"' in home
    slash = c.get("/console/dossier?dossier=a%2Fb")
    space = c.get("/console/dossier?dossier=a%20b")
    assert slash.status_code == 200 and space.status_code == 200
    assert "slash.pdf" in slash.text and "space.pdf" not in slash.text
    assert "space.pdf" in space.text and "slash.pdf" not in space.text


def test_an_unknown_dossier_answers_404_with_the_list(session_factory):
    with session_factory() as s:
        _doc(s, "bestaat", "a.pdf")
        s.commit()
    c = _client(session_factory)
    for name in ("bestaat-niet", "x/y"):
        r = c.get("/console/dossier", params={"dossier": name})
        assert r.status_code == 404, name
        assert 'href="/console/dossier?dossier=bestaat"' in r.text, name
        assert f"Dossier “{name}” bestaat niet." in r.text


def test_all_documents_keeps_the_full_list_reachable(session_factory):
    with session_factory() as s:
        _doc(s, "d", "in-dossier.pdf")
        _doc(s, None, "zonder-dossier.pdf")
        gone = _doc(s, None, "weg.pdf")
        delete_document(s, gone.id, InMemoryObjectStore(), InMemoryIndex(),
                        actor="test")
        s.commit()
    c = _client(session_factory)
    assert 'href="/console/documents"' in c.get("/console/dossier?dossier=d").text
    r = c.get("/console/documents")
    assert r.status_code == 200
    assert "in-dossier.pdf" in r.text and "zonder-dossier.pdf" in r.text
    assert 'href="/console/documents?alles=1"' in r.text   # the toggle moved too


def test_the_routes_live_in_their_own_module_under_the_limit():
    """tasks.md 1: console.py and dossiers.py do not grow (267 and 216 lines
    before this change); the new module stays within the contract."""
    lines = {p: len((SRC / p).read_text().splitlines())
             for p in ("console.py", "dossiers.py", "console_dossier.py",
                       "console_list.py")}
    assert lines["console.py"] <= 267 and lines["dossiers.py"] <= 216
    assert lines["console_dossier.py"] <= 200 and lines["console_list.py"] <= 200
