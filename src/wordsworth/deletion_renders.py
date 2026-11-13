# SPDX-License-Identifier: MIT
"""What a deletion removes of a document's redacted PDF (#451).

`GET /documents/{id}/redacted.pdf` caches its render in the object store
under ``redacted/<doc>/<render_version>/<boxmap_hash>`` and the box map it was
drawn from lives in `box_maps`. Both are derived from the document's content,
so they go with it: every object under the document's ``redacted/<doc>/``
prefix, and its `box_maps` row. Counted as `renders_removed` and
`box_maps_removed` in `DeletionCounts`, and so in the `deleted` record, the
API answer and the CLI output -- counts only, never a key's hash part.

Same order as the rest of `deletion.py`: the objects are an external side
effect the transaction cannot roll back and go first; the row goes inside the
caller's transaction. Removing what is already gone is a no-op, so a rerun
over an already-deleted document removes whatever was left (a render cached
before this module existed, or one a request was still writing while the
deletion committed). Such a rerun is not a transition, so `transition` writes
nothing for it; when it does remove something it appends one `remove-renders`
record (`deleted` -> `deleted`) with the actor and the two counts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Session

from . import audit
from .models import BoxMap
from .object_store import ObjectStore
from .pdf_redaction import redacted_prefix
from .states import State

if TYPE_CHECKING:
    from .deletion import DeletionCounts


@dataclass
class RenderCounts:
    """The two counts `DeletionCounts` inherits (a base class, so the change to
    `deletion.py` stays at one import, one base and one call)."""

    renders_removed: int = 0
    box_maps_removed: int = 0

    def render_counts(self) -> dict[str, int]:
        return {"renders_removed": self.renders_removed,
                "box_maps_removed": self.box_maps_removed}


def remove_renders(session: Session, document_id: UUID, store: ObjectStore,
                   counts: "DeletionCounts", *, actor: str, dry_run: bool) -> None:
    """Count (and, unless ``dry_run``, remove) the document's cached renders
    and its box map, writing the counts into ``counts``."""
    keys = [key for key, _ in store.iter_objects(redacted_prefix(document_id))]
    box_map = session.get(BoxMap, document_id)
    counts.renders_removed = len(keys)
    counts.box_maps_removed = int(box_map is not None)
    if dry_run:
        return
    for key in keys:
        store.delete(key)
    if box_map is not None:
        session.delete(box_map)
        session.flush()
    rerun = audit.current_state(session, document_id) == State.DELETED
    if rerun and (keys or box_map is not None):
        audit.append(session, document_id=document_id,
                     from_state=State.DELETED.value, to_state=State.DELETED.value,
                     step="remove-renders",
                     payload={"actor": actor, **counts.render_counts()})
