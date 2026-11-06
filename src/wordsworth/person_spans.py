"""Person-aggregate dedupe (person-aggregate-dedupe, step 3 of 4, split from
`detect-dutch-particle-names`, #285).

`ReversibleAnonymizer.anonymize` counts one audit-aggregate row per `PERSON`
detection (`stats.add` once per `Entity`, `pseudonymizer.py`). When GLiNER
returns the bare first name next to the full-name span for the same person,
that one person is counted twice. `drop_absorbed` removes the shorter
detection before the aggregate loop runs; it is never passed into
`_pseudonymize_entities`, so the anonymised text is unaffected.

Containment is by VALUE, not offset — like `_pseudonymize_entities`
(pseudonymizer.py), whose own comment records that the service's offsets do
not line up with Python slicing. A `PERSON` value A is absorbed into a longer
`PERSON` value B of the same entity list when A's words occur, in order and as
exact whole words, in B (`"Janine"` in `"Janine van Dijk"`; not `"Jan"`, which
is not itself one of B's words). Matching is exact — no case- or
diacritic-folding — for the same reason `_pseudonymize_entities` matches
exactly: the aggregate must not merge what the replacement treats as
different values. Equal values are not merged: the aggregate stays one row
per detection, unchanged from today. Only `PERSON` is touched; every other
label passes through untouched.
"""
from __future__ import annotations

from .openanonymiser_driver import Entity

_PERSON = "PERSON"


def _words(value: str) -> list[str]:
    return value.split()


def _contains_in_order(short_words: list[str], long_words: list[str]) -> bool:
    """Whether every word of `short_words` occurs in `long_words`, in the same
    order, as an exact whole word (no partial-word match, no reordering)."""
    remaining = iter(long_words)
    return all(any(word == other for other in remaining) for word in short_words)


def _is_absorbed(value: str, other_values: set[str]) -> bool:
    words = _words(value)
    for other in other_values:
        if other == value or len(other) <= len(value):
            continue
        if _contains_in_order(words, _words(other)):
            return True
    return False


def drop_absorbed(entities: list[Entity]) -> list[Entity]:
    """`entities` with every `PERSON` entity dropped whose value is absorbed
    into a longer `PERSON` value in the same list. Non-`PERSON` entities, and
    `PERSON` entities whose value is not absorbed, are returned unchanged and
    in their original order."""
    person_values = {e.text for e in entities if e.entity_type.upper() == _PERSON and e.text}
    absorbed = {value for value in person_values if _is_absorbed(value, person_values)}
    return [
        e for e in entities
        if not (e.entity_type.upper() == _PERSON and e.text in absorbed)
    ]
