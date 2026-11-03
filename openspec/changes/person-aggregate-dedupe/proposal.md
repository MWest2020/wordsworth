# person-aggregate-dedupe (step 3 of 4)

## Why

`ReversibleAnonymizer` builds its per-layer audit aggregate keyed by value
(`winner` in `src/wordsworth/pseudonymizer.py`). When GLiNER returns the bare
first name next to the full-name span, one person is counted twice. The
particle rule of step 1 makes this visible, but it is independent of it. Split
from `detect-dutch-particle-names` (#285); the 1 Nov architect called it the
separable part. Build after `particle-names-rule` has merged (it needs only
main to be green).

## What changes

- A pure helper module `src/wordsworth/person_spans.py` (≤200 lines, no I/O)
  that takes the aggregate's entity list and absorbs a shorter `PERSON` value
  into a longer one containing it. Named `person_spans` so it is not confused
  with the object-dedupe CLI `src/wordsworth/dedupe.py`.
- `pseudonymizer.py` calls it where the aggregate is built. Replacement in the
  text is unchanged.

## Impact

- Specs: `anonymization` (ADDED, one requirement).
- Code: `src/wordsworth/person_spans.py` (new), `src/wordsworth/pseudonymizer.py`
  (the call only).
- Tests: `tests/test_person_spans.py` (new), plus one test through
  `ReversibleAnonymizer`.
- Docs: `docs/reference/evaluation.md`, one paragraph on how the aggregate
  counts a person.
