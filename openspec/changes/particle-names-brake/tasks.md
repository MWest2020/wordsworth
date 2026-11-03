# Tasks

Step 2 of 4, split from `detect-dutch-particle-names` (#285). Build after
`particle-names-rule` has merged.

## 1. Corpus brake
- [ ] `tests/test_particle_names_veiligheid.py` generates the evaluation
      corpus (as `tests/test_allow_list_veiligheid.py` does) and, per shipped
      entry, asserts the entry occurred as a first name before a particle and
      last name (count > 0, failing by name otherwise), then that no false
      `PERSON` came from it. Proved by: the test, plus a negative control with
      a stub gazetteer holding `Zzyzx` that makes the occurrence assertion fail.

## 2. Fixture brake
- [ ] `tests/fixtures/gewone_zinnen_nl.txt`: Dutch sentences, one per line,
      `PERSON<TAB>…` or `GEEN<TAB>…` with a `{naam}` slot, at least one
      `PERSON` sentence per particle. The test runs every shipped entry over
      every sentence and asserts the stated expectation on the full-name
      substring, in the detection and in the anonymised output; a line without
      an expectation fails. Proved by: the test, a guard that every particle has
      a `PERSON` sentence whose detection occurs, and a negative control: a stub
      gazetteer holding `Ton` makes step 1's exclusion test fail.
- [ ] If an entry fails the brake, remove it from
      `src/wordsworth/data/voornamen.json` in this change and say so in the PR.

## 3. Docs
- [ ] `docs/how-to/detection-lists.md`: the brake (corpus and fixture, the
      expectation format, that it proves exercise and no `Ton`-shaped entry, not
      coverage). Proved by: the paragraph names the test file and the fixture.

## 4. Check
- [ ] `openspec validate particle-names-brake --strict` passes.
- [ ] `uv run ruff check src/ tests/` is clean and the full test suite passes.
