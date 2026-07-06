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


TERMINAL: frozenset[State] = frozenset(
    {State.UNPROCESSABLE_OCR, State.INDEXED, State.FAILED}
)

# Allowed transitions. None = the document does not exist yet. FAILED is
# reachable from every non-terminal state. Terminal states have no outgoing edge.
ALLOWED: dict[State | None, frozenset[State]] = {
    None: frozenset({State.REGISTERED}),
    State.REGISTERED: frozenset(
        {State.EXTRACTABLE, State.UNPROCESSABLE_OCR, State.FAILED}
    ),
    State.EXTRACTABLE: frozenset({State.EXTRACTED, State.FAILED}),
    State.EXTRACTED: frozenset({State.ANONYMIZED, State.FAILED}),
    State.ANONYMIZED: frozenset({State.INDEXED, State.FAILED}),
}


def is_allowed(frm: State | None, to: State) -> bool:
    return to in ALLOWED.get(frm, frozenset())
