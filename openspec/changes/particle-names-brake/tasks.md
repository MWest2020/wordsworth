# Tasks

Step 2 of 4, split from `detect-dutch-particle-names` (#285). Build after
`particle-names-rule` has merged.

## 1. Corpus brake
- [ ] `tests/test_particle_names_veiligheid.py` generates the evaluation
      corpus (as `tests/test_allow_list_veiligheid.py` does) and, per shipped
      entry, asserts the entry occurred as a first name before a particle and
      last name (count > 0, failing by name otherwise), then that no false
      `PERSON` came from it. A hit fails with a message naming the entry and
      edits nothing. Proved by: the test, plus a negative control (in
      `tests/test_particle_names_zinnen.py`) with a stub gazetteer holding
      `Zzyzx` that makes the occurrence assertion fail.
- [ ] The same file holds the coverage guard: every particle has at least one
      `PERSON` sentence in the fixture whose detection occurs. Proved by: the
      test, run against a fixture copy with one particle's `PERSON` lines
      removed, which fails naming that particle.

## 2. Fixture brake
- [ ] `tests/fixtures/gewone_zinnen_nl.txt`: Dutch sentences, one per line,
      `PERSON<TAB>sentence<TAB>full name` or `GEEN<TAB>sentence` with a `{naam}`
      slot (also in the full name), at least one `PERSON` sentence per particle.
      Proved by: the coverage guard of task 1.
- [ ] `tests/test_particle_names_zinnen.py` runs every shipped entry over every
      sentence and asserts the stated expectation: for `PERSON`, a detection
      covering exactly the third-column full name, absent from the anonymised
      output; for `GEEN`, no `PERSON` from the rule. The test reads the full
      name from the third column and does not scan for particles. A line
      without an expectation, or a `PERSON` line without a third column, fails.
      Proved by: the test, plus a negative control: a stub gazetteer holding
      `Ton` makes step 1's exclusion test fail.
- [ ] A brake hit never edits `src/wordsworth/data/voornamen.json`. Proved by:
      neither test file opens that file for writing (the test, via a read-only
      check of the path in the failure message), and the diff of this change
      does not touch it.

## 3. Docs
- [ ] `docs/how-to/detection-lists.md`: the brake (corpus and fixture, the
      expectation format with the third column, that a hit fails and names the
      entry without editing the gazetteer, that it proves exercise and no
      `Ton`-shaped entry, not coverage). Proved by: the paragraph names both
      test files and the fixture.

## 4. Check
- [ ] Both test files stay under 200 lines. Proved by: `wc -l` on each.
- [ ] `openspec validate particle-names-brake --strict` passes.
- [ ] `uv run ruff check src/ tests/` is clean and the full test suite passes.
