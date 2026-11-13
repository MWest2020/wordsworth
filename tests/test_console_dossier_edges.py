# SPDX-License-Identifier: MIT
"""The dossier home at its edges (console-dossier-home, review of #426)."""
from fastapi.testclient import TestClient

from wordsworth import dossiers
from wordsworth.api import create_app
from wordsworth.deletion import delete_document
from wordsworth.models import DocumentText, Topic
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex

KEYS = {"s3cret": "mark"}
HTML = {"Accept": "text/html"}


def _client(session_factory, index=None, **kw):
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                              search_index=index, **kw),
                   follow_redirects=False, base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    return c


def _doc(session, dossier, name, index=None, topics=()):
    d = register(session, f"documents/{name}", filename=name)
    session.merge(DocumentText(document_id=d.id, anonymized_text="woord"))
    dos = dossiers.ensure(session, dossier)
    dossiers.add(session, dos.id, d.id, actor="test")
    if index is not None:
        index.index(str(d.id), "woord", d.object_key, dossiers=[str(dos.id)],
                    topics=[str(t) for t in topics])
    session.flush()
    return d


def test_a_dossier_with_a_comma_searches_itself_not_its_parts(session_factory):
    """Review I1: from the 'a,b' page, the question box and the topic link
    answered with the documents of 'a' and 'b', and none of its own."""
    index = InMemoryIndex()
    with session_factory() as s:
        _doc(s, "a", "van-a.pdf", index)
        _doc(s, "b", "van-b.pdf", index)
        topic = Topic(dossier_id=dossiers.ensure(s, "a,b").id,
                      computed_name="t", document_count=1)
        s.add(topic)
        s.flush()
        _doc(s, "a,b", "van-ab.pdf", index, topics=[topic.id])
        s.commit()
        topic_id = topic.id
    c = _client(session_factory, index)
    page = c.get("/console/dossier?dossier=a%2Cb").text
    assert f'href="/console/search?dossier=a%2Cb&amp;topic={topic_id}"' in page
    for url in ("/console/search?dossier=a%2Cb&q=woord",
                f"/console/search?dossier=a%2Cb&topic={topic_id}&q=woord"):
        hits = c.get(url).text
        assert "van-ab.pdf" in hits, url
        assert "van-a.pdf" not in hits and "van-b.pdf" not in hits, url


def test_no_dossier_named_goes_back_to_the_home_page(session_factory):
    c = _client(session_factory)
    for url in ("/console/dossier", "/console/dossier?dossier="):
        r = c.get(url)
        assert r.status_code == 303 and r.headers["location"] == "/console", url


def test_the_new_routes_sit_behind_the_same_doors(session_factory):
    with session_factory() as s:
        _doc(s, "d", "a.pdf")
        s.commit()
    anon = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                      follow_redirects=False, base_url="https://testserver")
    reader = _client(session_factory, corpus_read_labels=["iemand-anders"])
    for path in ("/console", "/console/dossier?dossier=d", "/console/documents"):
        assert anon.get(path).status_code == 401, path
        assert anon.get(path, headers=HTML).headers["location"] == "/console/login"
        assert reader.get(path).status_code == 403, path


def test_dossier_and_topic_names_are_escaped(session_factory):
    evil = "<script>alert(1)</script>"
    with session_factory() as s:
        _doc(s, evil, "a.pdf")
        _doc(s, "ander", "b.pdf")
        s.add(Topic(dossier_id=dossiers.ensure(s, evil).id, computed_name="x",
                    given_name=evil, document_count=1))
        s.commit()
    c = _client(session_factory)
    home = c.get("/console").text
    page = c.get("/console/dossier", params={"dossier": evil})
    unknown = c.get("/console/dossier", params={"dossier": evil + "!"})
    assert page.status_code == 200 and unknown.status_code == 404
    for text in (home, page.text, unknown.text):
        assert evil not in text and "&lt;script&gt;" in text


def test_names_with_ampersand_hash_percent_and_unicode_resolve(session_factory):
    names = ["R&D", "zaak #3", "100% zeker", "Ĳsselmeer – café"]
    with session_factory() as s:
        for n, name in enumerate(names):
            _doc(s, name, f"doc-{n}.pdf")
        s.commit()
    c = _client(session_factory)
    home = c.get("/console").text
    for n, name in enumerate(names):
        href = home.split(f">{name.replace('&', '&amp;')}</a>")[0]
        href = href.rsplit('href="', 1)[1].rstrip('"')
        assert "&" not in href.split("?", 1)[1] and "#" not in href, href
        page = c.get(href)
        assert page.status_code == 200, name
        assert f"doc-{n}.pdf" in page.text, name
        assert sum(f"doc-{m}.pdf" in page.text for m in range(4)) == 1, name


def test_the_dossier_page_caps_at_200_and_says_how_many(session_factory):
    with session_factory() as s:
        for n in range(201):
            _doc(s, "groot", f"g{n:03}.pdf")
        s.commit()
    page = _client(session_factory).get("/console/dossier?dossier=groot").text
    assert "201 documenten · nieuwste 200" in page
    assert page.count('href="/console/documents/') == 200


def test_topics_counting_more_than_the_live_documents_say_they_are_stale(
        session_factory):
    """Review M1: after deletions, '3 van 1' is not a coverage; say why and
    where to recompute, without clamping the number."""
    with session_factory() as s:
        docs = [_doc(s, "d/e", f"{n}.pdf") for n in range(3)]
        s.add(Topic(dossier_id=dossiers.ensure(s, "d/e").id, computed_name="t",
                    document_count=3))
        for d in docs[1:]:
            delete_document(s, d.id, InMemoryObjectStore(), InMemoryIndex(),
                            actor="test")
        s.commit()
    page = _client(session_factory).get("/console/dossier?dossier=d%2Fe").text
    assert "De onderwerpen tellen 3\n documenten, het dossier heeft er nu 1" in page
    assert "sinds de berekening zijn\n documenten verwijderd" in page
    assert 'href="/console/topics?dossier=d%2Fe">Bereken de onderwerpen opnieuw' in page
    assert "vallen in een onderwerp" not in page
