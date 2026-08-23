"""Nextcloud source end-to-end through the real pipeline (DB-integration, CI)."""
from __future__ import annotations

import hashlib

from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.nextcloud_source import ingest_from_nextcloud
from wordsworth.pipeline import ingest, process


class _FakeWebDav:
    def __init__(self, files):
        self._files = files

    def list_files(self, folder="/"):
        return sorted(self._files)

    def fetch(self, path):
        return self._files[path]


def _ingest_one(session, store, index, embedder):
    def run(data: bytes) -> dict:
        key = "documents/" + hashlib.sha256(data).hexdigest()
        if index.has_object_key(key):
            return {"state": "skipped"}
        doc = ingest(session, store, data)
        session.commit()
        st = process(session, doc.id, store, anonymizer=DeterministicAnonymizer(),
                     search_index=index, embedder=embedder)
        session.commit()
        return {"state": st.value}
    return run


def test_pull_ingests_pdfs_idempotent_and_continues(session, mem_store, mem_index,
                                                    fake_embedder, born_digital_pdf,
                                                    corrupt_pdf):
    client = _FakeWebDav({
        "/a.pdf": born_digital_pdf,
        "/b.pdf": born_digital_pdf,   # identical -> content-addressed skip
        "/c.pdf": corrupt_pdf,        # fails extraction -> failed, others continue
        "/notes.txt": b"x",           # non-PDF -> skipped, never ingested
    })
    one = _ingest_one(session, mem_store, mem_index, fake_embedder)

    s1 = ingest_from_nextcloud(client, one, "/")
    assert s1 == {"found": 3, "ingested": 1, "skipped": 2, "failed": 1}
    assert len(mem_index._docs) == 1                      # only the one unique PDF

    # Re-run: the indexed PDF(s) are skipped; nothing new ingested (idempotent).
    s2 = ingest_from_nextcloud(client, one, "/")
    assert s2["ingested"] == 0 and s2["skipped"] == 2 and s2["failed"] == 1
