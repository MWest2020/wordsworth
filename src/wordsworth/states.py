"""The document state machine: states, terminal states, and allowed edges."""
from __future__ import annotations

from enum import Enum


class State(str, Enum):
    REGISTERED = "registered"
    EXTRACTABLE = "extractable"
    UNPROCESSABLE_OCR = "unprocessable_ocr"
    EXTRACTED = "extracted"
    ANONYMIZED = "anonymized"
    INDEXED = "indexed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


TERMINAL: frozenset[State] = frozenset({State.INDEXED, State.FAILED, State.SUPERSEDED})

# Allowed transitions. None = the document does not exist yet. FAILED is
# reachable from every non-terminal state. Terminal states have no outgoing
# edge, with ONE exception, named here rather than bent quietly: `superseded`
# is reachable from every state, the terminal ones included. A copy of an
# object that is already a document is retired, whatever state it reached
# (one-document-per-object); `superseded` itself has no way out.
# `unprocessable_ocr` is a resting state, not terminal: the born-digital pass
# leaves a document there, and the opt-in OCR recovery step (add-ocr) is its one
# outgoing edge back into the searchable flow (-> extractable).
_EDGES: dict[State | None, frozenset[State]] = {
    None: frozenset({State.REGISTERED}),
    State.REGISTERED: frozenset(
        {State.EXTRACTABLE, State.UNPROCESSABLE_OCR, State.FAILED}
    ),
    State.UNPROCESSABLE_OCR: frozenset({State.EXTRACTABLE}),
    State.EXTRACTABLE: frozenset({State.EXTRACTED, State.FAILED}),
    State.EXTRACTED: frozenset({State.ANONYMIZED, State.FAILED}),
    State.ANONYMIZED: frozenset({State.INDEXED, State.FAILED}),
    State.INDEXED: frozenset(),
    State.FAILED: frozenset(),
}
ALLOWED: dict[State | None, frozenset[State]] = {
    frm: to | ({State.SUPERSEDED} if frm is not None else frozenset())
    for frm, to in _EDGES.items()
}


def is_allowed(frm: State | None, to: State) -> bool:
    return to in ALLOWED.get(frm, frozenset())
