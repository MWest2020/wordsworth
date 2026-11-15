# SPDX-License-Identifier: MIT
"""#466 (1): the API's already-indexed ingest path racing a dossier deletion.

Bytes that are already in the index are not ingested again; a delivery into
another dossier only adds that membership. That path took no row lock, so a
dossier deletion that had already decided to delete the document (its only
dossier being the one deleted) still deleted it after the membership was
added -- a deleted document left as a member of the other dossier. Now the
path locks the row FOR SHARE and checks liveness again, as `ingest` does
(`ingest_lock.lock_live_for`)."""
from __future__ import annotations

import threading

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from race_setup import run
from test_reanonymize_delete_race import _done_or_waiting
from wordsworth import dossiers
from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.api import create_app
from wordsworth.audit import current_state, verify_chain
from wordsworth.dossier_deletion import delete_dossier
from wordsworth.models import Document, DossierDocument
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


class _HoldingIndex(InMemoryIndex):
    """Runs ``on_exists`` once, on the next `exists`: where a deletion holds
    its rows and has removed nothing yet -- the entry is still in the index."""

    on_exists = None

    def exists(self, document_id):
        hook, self.on_exists = self.on_exists, None
        if hook is not None:
            hook()
        return super().exists(document_id)


def test_a_delivery_does_not_join_a_document_being_deleted(
        session_factory, mem_store, born_digital_pii_pdf, fake_embedder):
    index = _HoldingIndex()
    client = TestClient(create_app(
        session_factory=session_factory, store=mem_store, search_index=index,
        embedder=fake_embedder, anonymizer=DeterministicAnonymizer()))

    def deliver(dossier):
        return client.post("/ingest", params={"dossier": dossier}, files={
            "files": ("a.pdf", born_digital_pii_pdf, "application/pdf")})

    first = deliver("zaak-a")
    assert first.status_code == 200, first.text
    old_id = first.json()["results"][0]["document_id"]
    with session_factory() as s:
        dossier_a = dossiers.ensure(s, "zaak-a").id
        s.commit()
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()

    def hold():
        paused.set()
        assert resume.wait(30), "never resumed"

    def deleting_dossier():
        with session_factory() as s:
            s.execute(text("SET lock_timeout = '20s'"))
            index.on_exists = hold  # rows held, the member classified: delete
            delete_dossier(s, dossier_a, mem_store, index, actor="t")
            s.commit()

    def delivering():
        result["response"] = deliver("zaak-b")

    dele = run(errors, "delete-dossier", deleting_dossier)
    assert paused.wait(10)
    deli = run(errors, "deliver", delivering)
    try:
        # Before the fix the delivery simply finishes here; now it waits.
        _done_or_waiting(session_factory, deli)
    finally:
        resume.set()
        dele.join(30)
        deli.join(30)

    assert not errors, errors
    response = result["response"]
    assert response.status_code == 200, response.text
    outcome = response.json()["results"][0]
    with session_factory() as s:
        assert current_state(s, old_id) == State.DELETED
        members = s.execute(select(DossierDocument.document_id)).scalars().all()
        # No deleted document is anybody's member ...
        assert all(current_state(s, m) != State.DELETED for m in members)
        # ... and the delivery was not lost: the bytes are a new document in B.
        assert outcome["document_id"] != old_id
        assert outcome["state"] == State.INDEXED.value
        new = s.get(Document, outcome["document_id"])
        assert [str(m) for m in members] == [str(new.id)]
        assert index.exists(str(new.id)) and not index.exists(old_id)
        assert verify_chain(s) == (True, None)


def test_a_deleted_document_still_holding_its_key_names_the_way_out(
        session_factory, mem_store, born_digital_pii_pdf, fake_embedder):
    """#466 review: "attempts exhausted" is not "no document". A document
    deleted before deletions released the object key, with its content still
    in the index, is refused with the text that names the remedy -- not
    ingested again over a key it cannot have."""
    import hashlib

    from wordsworth.deletion import delete_document
    from wordsworth.ingest_lock import IngestRaceError

    index = InMemoryIndex()
    client = TestClient(create_app(
        session_factory=session_factory, store=mem_store, search_index=index,
        embedder=fake_embedder, anonymizer=DeterministicAnonymizer()))
    files = {"files": ("a.pdf", born_digital_pii_pdf, "application/pdf")}
    first = client.post("/ingest", params={"dossier": "zaak-a"}, files=files)
    doc_id = first.json()["results"][0]["document_id"]
    key = "documents/" + hashlib.sha256(born_digital_pii_pdf).hexdigest()
    with session_factory() as s:
        delete_document(s, doc_id, mem_store, index, actor="t")
        s.commit()
        s.get(Document, doc_id).object_key = key  # as before the release
        s.commit()
    index.index(doc_id, "tekst", key)  # and the index still knows the content
    with session_factory() as s:
        before = s.execute(select(DossierDocument.dossier_id)).scalars().all()

    r = client.post("/ingest", params={"dossier": "zaak-b"}, files={
        "files": ("a.pdf", born_digital_pii_pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    result = r.json()["results"][0]
    assert (result["state"], result["error"]) == ("error", IngestRaceError.public)
    assert "wordsworth-release-deleted-keys" in result["error"]
    with session_factory() as s:
        assert s.execute(select(DossierDocument.dossier_id)).scalars().all() == before
