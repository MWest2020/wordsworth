# SPDX-License-Identifier: MIT
"""Dossiers at the endpoints, and the existing corpus (dossier-scope).

Split from `test_dossiers` at the seam where the tests stop being about the
model and start being about what a caller sees.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth import dossiers
from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.api import create_app
from wordsworth.models import Document
from wordsworth.pipeline import dossiers_of, register
from wordsworth.search_index import InMemoryIndex


# --- the endpoints ---------------------------------------------------------

def _app(session_factory, index):
    return TestClient(create_app(session_factory=session_factory,
                                 search_index=index))


def test_searching_without_a_scope_is_refused(session_factory):
    index = InMemoryIndex()
    index.index("a", "vergunning", "ka", None, ["d1"])
    r = _app(session_factory, index).get("/search", params={"q": "vergunning"})
    assert r.status_code == 400
    assert "alle" in r.json()["detail"]


def test_searching_a_dossier_answers_from_it_only(session_factory):
    with session_factory() as s:
        a, b = dossiers.ensure(s, "zaak-a"), dossiers.ensure(s, "zaak-b")
        ida, idb = str(a.id), str(b.id)
        s.commit()
    index = InMemoryIndex()
    index.index("a", "vergunning hier", "ka", None, [ida])
    index.index("b", "vergunning elders", "kb", None, [idb])
    c = _app(session_factory, index)
    body = c.get("/search", params={"q": "vergunning", "dossier": "zaak-a"}).json()
    assert [h["document_id"] for h in body["hits"]] == ["a"]
    assert body["dossier"] == "zaak-a"
    alles = c.get("/search", params={"q": "vergunning", "dossier": "alle"}).json()
    assert {h["document_id"] for h in alles["hits"]} == {"a", "b"}


def test_an_unknown_dossier_is_a_400_and_not_an_empty_result(session_factory):
    """Empty results and a typo'd scope look identical to a reader, and one of
    them means 'nothing matched'."""
    index = InMemoryIndex()
    r = _app(session_factory, index).get(
        "/search", params={"q": "x", "dossier": "bestaat-niet"})
    assert r.status_code == 400 and "bestaat-niet" in r.json()["detail"]


def test_without_a_database_search_keeps_working_unscoped(session_factory):
    """A deployment with an index and no database has no dossiers to scope to.
    Requiring a scope it cannot satisfy would make search unusable — so this
    configuration searches everything, and the spec says so."""
    index = InMemoryIndex()
    index.index("a", "vergunning", "ka")
    c = TestClient(create_app(search_index=index))
    assert c.get("/search", params={"q": "vergunning"}).status_code == 200


def test_ingesting_without_a_dossier_is_refused(session_factory, mem_store,
                                                fake_embedder,
                                                born_digital_pii_pdf):
    """A document that belongs to no dossier is invisible to every scoped
    search, so letting it be optional would quietly make unfindable documents."""
    c = TestClient(create_app(session_factory=session_factory, store=mem_store,
                              search_index=InMemoryIndex(),
                              embedder=fake_embedder,
                              anonymizer=DeterministicAnonymizer()))
    r = c.post("/ingest", files={"files": ("a.pdf", born_digital_pii_pdf,
                                           "application/pdf")})
    assert r.status_code == 400 and "dossier" in r.json()["detail"]


def test_ingesting_known_bytes_into_another_dossier_adds_the_membership(
        session_factory, mem_store, fake_embedder, born_digital_pii_pdf):
    """The idempotent skip is about not re-processing. Swallowing the membership
    would make the skip eat the one thing the request was asking for."""
    index = InMemoryIndex()
    c = TestClient(create_app(session_factory=session_factory, store=mem_store,
                              search_index=index, embedder=fake_embedder,
                              anonymizer=DeterministicAnonymizer()))
    files = {"files": ("a.pdf", born_digital_pii_pdf, "application/pdf")}
    first = c.post("/ingest", params={"dossier": "zaak-a"}, files=files)
    assert first.status_code == 200, first.text
    second = c.post("/ingest", params={"dossier": "zaak-b"},
                    files={"files": ("a.pdf", born_digital_pii_pdf,
                                     "application/pdf")})
    assert second.status_code == 200, second.text
    assert second.json()["results"][0]["state"] == "added_to_dossier"

    with session_factory() as s:
        docs = s.execute(select(Document)).scalars().all()
        assert len(docs) == 1
        assert len(dossiers_of(s, docs[0].id)) == 2
        ids = {d["name"]: d["id"] for d in dossiers.listing(s)}
    # and the index learned it: the document is now reachable from zaak-b,
    # which it was not before the second delivery
    doc_id = str(docs[0].id)
    assert ids["zaak-b"] in index._dossiers[doc_id]
    assert ids["zaak-a"] in index._dossiers[doc_id]


# --- the existing corpus ---------------------------------------------------

def test_documents_from_before_dossiers_are_adopted_and_reindexed(session):
    """A scope that makes the existing corpus unfindable is not a migration but
    a loss — so the index has to learn the membership here, or a scoped search
    still cannot reach them."""
    from wordsworth.backfill_dossier import adopt, orphans
    from wordsworth.models import DocumentText

    oud = register(session, "documents/aa", filename="oud.pdf")
    session.merge(DocumentText(document_id=oud.id, anonymized_text="een besluit"))
    zonder_tekst = register(session, "documents/bb")
    al_geplaatst = register(session, "documents/cc")
    dossiers.add(session, dossiers.ensure(session, "zaak").id, al_geplaatst.id)
    session.commit()

    assert {d.id for d in orphans(session)} == {oud.id, zonder_tekst.id}

    index = InMemoryIndex()
    # Zoals in productie: het document stond al in de index, alleen zonder
    # dossier. De adoptie werkt het dossierveld bij en raakt de rest niet aan.
    index.index(str(oud.id), "een besluit", "documents/aa", [0.5])
    stats = adopt(session, "corpus-2026-09", index)
    session.commit()
    assert stats["adopted"] == 2
    assert stats["reindexed"] == 1 and stats["without_text"] == 1

    ids = {d["name"]: d["id"] for d in dossiers.listing(session)}
    assert index.search("besluit", only=[ids["corpus-2026-09"]])
    assert index._docs[str(oud.id)][2] == [0.5]      # de vector overleefde
    # and the document that was already placed stayed where it was
    assert dossiers_of(session, al_geplaatst.id) == [ids["zaak"]]


def test_adopting_twice_places_nothing_the_second_time(session):
    from wordsworth.backfill_dossier import adopt

    register(session, "documents/aa")
    session.commit()
    assert adopt(session, "corpus")["adopted"] == 1
    session.commit()
    tweede = adopt(session, "corpus")
    assert tweede["adopted"] == 0 and tweede["already_placed"] is True


def test_without_an_index_the_memberships_are_still_written(session):
    """The caller is told a reindex is outstanding; the data is not held hostage
    to a search engine being reachable."""
    from wordsworth.backfill_dossier import adopt

    d = register(session, "documents/aa")
    session.commit()
    stats = adopt(session, "corpus", None)
    session.commit()
    assert stats["adopted"] == 1 and stats["reindexed"] == 0
    assert len(dossiers_of(session, d.id)) == 1


def test_the_client_refuses_to_search_or_ingest_without_a_dossier():
    """The CLI is where a forgotten scope is easiest to make, so argparse itself
    refuses rather than the server having to."""
    from wordsworth.client import main

    for argv in (["search", "x"], ["hybrid", "x"], ["ingest", "/tmp"]):
        with pytest.raises(SystemExit) as exc:
            main(["--url", "http://x", *argv])
        assert exc.value.code == 2


def test_the_client_puts_the_dossier_in_the_ingest_url(monkeypatch, tmp_path):
    from wordsworth import client

    (tmp_path / "x.pdf").write_bytes(b"%PDF-1.4")
    gezien = {}

    def fake_urlopen(req, timeout=0):
        gezien["url"] = req.full_url

        class R:
            def read(self):
                return b'{"results": [{"filename": "x.pdf", "state": "indexed"}]}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return R()

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    client.main(["--url", "http://x", "ingest", str(tmp_path),
                 "--dossier", "zaak-a"])
    assert "dossier=zaak-a" in gezien["url"]


# --- two faults found by running it against production ---------------------

def test_a_dry_run_does_not_touch_the_index(session, monkeypatch, capsys):
    """The database can be rolled back; the index cannot. The first dry run
    against production wrote 770 documents, which made "dry" a lie."""
    from wordsworth import backfill_dossier

    geschreven = []

    class Index:
        def ensure_ready(self):
            pass

        def index(self, *a, **kw):
            geschreven.append(a)

    monkeypatch.setattr(
        "wordsworth.opensearch_index.OpenSearchIndex.from_config",
        classmethod(lambda cls: Index()))
    register(session, "documents/aa")
    session.commit()
    monkeypatch.setattr(backfill_dossier, "make_engine", lambda: None)
    monkeypatch.setattr(backfill_dossier, "make_session_factory",
                        lambda e: (lambda: _Keep(session)))
    backfill_dossier.main(["corpus", "--dry-run"])
    assert geschreven == []
    assert "NIET aangeraakt" in capsys.readouterr().err


class _Keep:
    """A session that survives `with`, so the CLI can use the test's session."""

    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *a):
        return False


def test_a_field_missing_from_an_existing_index_is_added():
    """`indices.create` only runs for a new index, so a field added to the
    mapping later never reaches an existing one — and a string array then maps
    dynamically as `text`, where a terms filter matches nothing and the search
    returns zero hits with no error."""
    from wordsworth.opensearch_index import OpenSearchIndex

    put = {}

    class Client:
        class indices:
            @staticmethod
            def exists(index):
                return True

            @staticmethod
            def get_mapping(index):
                return {index: {"mappings": {"properties": {"text": {"type": "text"}}}}}

            @staticmethod
            def put_mapping(index, body):
                put.update(body)

    OpenSearchIndex(Client(), "ww", 64).ensure_ready()
    assert put["properties"]["dossiers"] == {"type": "keyword"}
    assert "text" not in put["properties"]        # only what was missing


def test_a_field_with_the_wrong_type_is_a_hard_error():
    """A field cannot be retyped in place. Carrying on would leave a filter that
    silently matches nothing, and that reads as "no results"."""
    from wordsworth.opensearch_index import MappingConflict, OpenSearchIndex

    class Client:
        class indices:
            @staticmethod
            def exists(index):
                return True

            @staticmethod
            def get_mapping(index):
                return {index: {"mappings": {"properties": {
                    "dossiers": {"type": "text"}}}}}

            @staticmethod
            def put_mapping(index, body):
                pass

    with pytest.raises(MappingConflict) as exc:
        OpenSearchIndex(Client(), "ww", 64).ensure_ready()
    assert "dossiers" in str(exc.value) and "reindex" in str(exc.value)
