# SPDX-License-Identifier: MIT
"""Een lidmaatschapswijziging mag niets anders aanraken.

Op 2026-09-18 verloren 770 documenten in productie hun embedding. Niet door een
fout maar door een vorm: `index()` bouwt een vers document, dus wie `vector=`
weglaat wist de vector — zonder fout, zonder auditrecord, alleen resultaten die
er niet meer zijn. De codereview vond het; de meting bevestigde het (770 in de
index, 0 met vector).

Deze tests bewaken de vorm die dat onmogelijk maakt.
"""
import pytest
from fastapi.testclient import TestClient

from wordsworth import dossiers
from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.api import create_app
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex

PDF = b"%PDF-1.4 een besluit"


def test_changing_dossiers_keeps_text_and_vector():
    index = InMemoryIndex()
    index.index("a", "de tekst", "key-a", [0.1, 0.2], ["d1"])
    index.set_dossiers("a", ["d2"])
    tekst, key, vector = index._docs["a"]
    assert tekst == "de tekst" and key == "key-a" and vector == [0.1, 0.2]
    assert index._dossiers["a"] == {"d2"}


def test_a_second_delivery_does_not_drop_the_embedding(session_factory, mem_store,
                                                       fake_embedder,
                                                       born_digital_pii_pdf):
    """Reproduced by the review and confirmed in production: the second ingest
    reported success and silently removed the document from the kNN half."""
    index = InMemoryIndex()
    c = TestClient(create_app(session_factory=session_factory, store=mem_store,
                              search_index=index, embedder=fake_embedder,
                              anonymizer=DeterministicAnonymizer()))
    files = lambda: {"files": ("a.pdf", born_digital_pii_pdf, "application/pdf")}
    c.post("/ingest", params={"dossier": "zaak-a"}, files=files())
    doc_id = next(iter(index._docs))
    assert index._docs[doc_id][2] is not None, "na de eerste levering"

    r = c.post("/ingest", params={"dossier": "zaak-b"}, files=files())
    assert r.json()["results"][0]["state"] == "added_to_dossier"
    assert index._docs[doc_id][2] is not None, "de vector overleeft de tweede"
    assert len(index._dossiers[doc_id]) == 2


def test_content_indexed_without_its_document_is_a_conflict(session_factory,
                                                            mem_store,
                                                            fake_embedder,
                                                            born_digital_pii_pdf):
    """The index can know content the database does not — a restored index, or
    one pointed at a fresh database. Reporting "skipped" there claims a success
    the request did not have: no dossier was created and nothing was added.

    Note how this had to be built. A document CANNOT be deleted while its audit
    records exist (the trail is append-only and holds a foreign key), so the
    case is only reachable through the index, never by removing a row. That is
    the invariant doing its job."""
    import hashlib

    index = InMemoryIndex()
    key = "documents/" + hashlib.sha256(born_digital_pii_pdf).hexdigest()
    index.index("spook", "tekst van een document dat hier niet bestaat", key)

    c = TestClient(create_app(session_factory=session_factory, store=mem_store,
                              search_index=index, embedder=fake_embedder,
                              anonymizer=DeterministicAnonymizer()))
    body = c.post("/ingest", params={"dossier": "zaak-b"},
                  files={"files": ("a.pdf", born_digital_pii_pdf,
                                   "application/pdf")}).json()
    r = body["results"][0]
    assert r["state"] == "error", r
    with session_factory() as s:
        from sqlalchemy import select

        from wordsworth.models import Dossier
        assert s.execute(select(Dossier)).scalars().all() == []


def test_assign_updates_the_index_so_the_move_is_real(session):
    """The spec scenario: a search on the old dossier no longer finds it, one on
    the new dossier does. The first version of this command changed only the
    database, so neither was true."""
    from wordsworth.dossier_tools import assign

    index = InMemoryIndex()
    oud = dossiers.ensure(session, "verkeerd")
    doc = register(session, "documents/a", filename="a.pdf")
    session.commit()
    dossiers.add(session, oud.id, doc.id)
    index.index(str(doc.id), "een besluit", "documents/a", [0.5], [str(oud.id)])

    besluit = "https://open.gelderland.nl/woo-documenten/woo-besluit-over-iets"
    assign(session, {"a.pdf": besluit}, weg_uit="verkeerd", index=index)
    session.commit()

    nieuw = dossiers.resolve(session, "woo besluit over iets")[0]
    assert index.search("besluit", only=[str(oud.id)]) == []
    assert [h.document_id for h in index.search("besluit", only=[str(nieuw)])] == [str(doc.id)]
    assert index._docs[str(doc.id)][2] == [0.5]      # and the vector survived


def test_a_document_not_in_the_index_is_reported_not_created():
    """A membership change updates what exists. Indexing a document that never
    got through the straat would bury a different problem under this one."""
    index = InMemoryIndex()
    assert index.set_dossiers("bestaat-niet", ["d1"]) is False
    assert index.search("") == []


def test_the_opensearch_driver_reports_a_missing_document_the_same_way():
    from wordsworth.opensearch_index import OpenSearchIndex

    class Weg(Exception):
        status_code = 404

    class Client:
        def update(self, **kw):
            raise Weg()

    assert OpenSearchIndex(Client(), "ww", 64).set_dossiers("x", ["d"]) is False


def test_any_other_index_failure_is_raised_not_swallowed():
    """A 404 means "not there". Anything else means we do not know, and a write
    that quietly did nothing is the worst of both."""
    from wordsworth.opensearch_index import OpenSearchIndex

    class Stuk(Exception):
        status_code = 503

    class Client:
        def update(self, **kw):
            raise Stuk()

    with pytest.raises(Stuk):
        OpenSearchIndex(Client(), "ww", 64).set_dossiers("x", ["d"])
