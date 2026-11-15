# SPDX-License-Identifier: MIT
"""A delivery of bytes that are already in the search index (the API's
`/ingest`): nothing is ingested again, but a delivery into ANOTHER dossier
still has to add that membership, or the skip would silently swallow the one
thing the request was asking for.

The index, not the database, is the source of truth for "searchable", so this
stays correct when the index was recreated: those documents are eligible for
a full ingest again.

It adds to an existing document without going through `pipeline.ingest`, so
it locks the document's row itself (`ingest_lock.lock_live_for`, #466;
`docs/reference/lock-order.md`). Without that a dossier deletion in flight,
which had already decided to delete the document, deleted it after the
membership was added here: a deleted document left as a member.
"""
from __future__ import annotations

from fastapi import HTTPException

from . import dossiers
from .ingest_lock import lock_live_for
from .pipeline import dossiers_of
from .search_index import SearchIndex


def deliver(session_factory, search_index: SearchIndex, object_key: str,
            dossier: str | None) -> dict | None:
    """The result for a delivery of already-indexed bytes, or None when they
    are not (or no longer) in the index and the caller has to ingest them.

    - A live document: its membership of ``dossier`` is added if it was not
      one; `added_to_dossier` or `skipped`.
    - No live document and the index entry gone too: the document was
      deleted while this waited for its row. None -- these bytes are a new
      document, as for a request arriving a moment later.
    - No live document but the index still knows the content: 409; "skipped"
      would claim a success this request did not have.
    - A document deleted before deletions released the object key still holds
      it: `IngestRaceError` from `lock_live_for`, whose fixed text names
      `wordsworth-release-deleted-keys`; the caller reports it as it does for
      `ingest`.
    """
    if not search_index.has_object_key(object_key):
        return None
    with session_factory() as session:
        # The live one: a superseded copy has the same key, and a membership
        # added to it would vanish from every scope.
        doc = lock_live_for(session, object_key)
        if doc is None:
            if not search_index.has_object_key(object_key):
                return None
            raise HTTPException(
                status_code=409,
                detail="content is indexed but its document is gone; "
                       "reindex before ingesting it again")
        # Actor "ingest": nobody moved this, it arrived. There is no endpoint
        # that changes a membership by hand, so a caller identity would be
        # borrowed from a different act.
        added = bool(dossier and dossiers.add(
            session, dossiers.ensure(session, dossier).id, doc.id, actor="ingest"))
        session.commit()
        if added:
            # A membership change touches ONLY the dossiers. Writing the whole
            # document back would drop the embedding of any caller who forgets
            # `vector=` -- which is exactly what cost 770 documents their
            # vectors on 2026-09-18.
            search_index.set_dossiers(str(doc.id), dossiers_of(session, doc.id))
        return {"state": "added_to_dossier" if added else "skipped",
                "document_id": str(doc.id)}
