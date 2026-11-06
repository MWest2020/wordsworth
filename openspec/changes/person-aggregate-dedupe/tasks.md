# Tasks

Step 3 of 4, split from `detect-dutch-particle-names` (#285).

## 1. Helper
- [ ] `src/wordsworth/person_spans.py` (≤200 lines, no I/O) with the
      containment rule of design.md. Proved by: `tests/test_person_spans.py`
      calling it directly on entity lists: bare first name plus full name (only
      the full-name rows remain), two people with the same first name (two
      rows, one per full name), equal values (one row per occurrence, as
      today), `"Jan"` vs `"Janine van Dijk"` (not absorbed), a non-PERSON label
      (untouched), a case or diacritic variant (not absorbed).

## 2. Wiring
- [ ] `ReversibleAnonymizer.anonymize` passes the entities through the helper
      only for the aggregate loop. Proved by: a test with a stub entity layer
      returning the bare first name and the full name, asserting the aggregate
      holds only the full-name row(s) for that person and that the anonymised output equals the output
      without the helper; and the diff shows `pseudonymizer.py` grew by the call
      only.

## 3. Docs
- [ ] `docs/reference/evaluation.md`: how the aggregate counts a person (by
      value, `PERSON` only, one row per detection of the longer value,
      replacement unaffected). Proved by: the paragraph
      names `tests/test_person_spans.py`.

## 4. Check
- [ ] `openspec validate person-aggregate-dedupe --strict` passes.
- [ ] `uv run ruff check src/ tests/` is clean and the full test suite passes.
