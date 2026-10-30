# Tasks

## 1. Detection
- [ ] New module (e.g. `src/wordsworth/particle_names.py`, ≤200 lines) with a
      deterministic pattern: gazetteer first name, particle (`van`, `de`, `ter`,
      `ten`, `van der`), capitalised last name, as ONE `PERSON` span, layer
      `dutch_particle_name`. Proved by: a new test file
      `tests/test_particle_names.py` with synthetic names, one example per
      particle, asserting one `PERSON` detection covering the whole name and
      layer `dutch_particle_name`.
- [ ] The rule runs in anonymisation. Proved by: a test in the same file that
      runs `ReversibleAnonymizer.anonymize` on a text with such a name and
      asserts neither first name, particle nor last name is in the output.
- [ ] The layer shows in the per-layer aggregates. Proved by: a test that the
      aggregates of that run hold a `dutch_particle_name` entry with a count
      and no value or offset.
- [ ] Ordinary text is not swallowed. Proved by: a test that a sentence with
      lowercase `de`/`van` between ordinary words yields no `PERSON`.
- [ ] Institutions are not names. Proved by: a parametrised test over `Raad van
      State`, `Kamer van Koophandel`, `Ministerie van Binnenlandse Zaken`,
      `Vereniging van Eigenaren` and `Hoogheemraadschap van Rijnland`, each in
      a sentence, asserting no `PERSON` is produced from them.
- [ ] The anchor is the gazetteer. Proved by: a test that a capitalised word
      not in the gazetteer before a particle (`<unlisted word> van <Word>`)
      yields no `PERSON`, and the same shape with a listed first name does.

## 2. Gazetteer
- [ ] A gazetteer data file with `{"naam", "reden"}` entries and a loader that
      refuses an entry without a reason (missing or blank). Proved by: a test
      that loading a file with an entry lacking `reden` raises, naming the
      entry, and a test that every entry of the shipped file has a non-empty
      reden.
- [ ] A missing or unreadable gazetteer is a hard error, not an empty list. No
      silent fallback. Proved by: a test that the rule fails loudly when the
      file is absent.

## 3. Outside the deterministic table
- [ ] Add no row to `detectors.DETECTORS`. Proved by: a test asserting the set of
      labels in `DETECTORS` is still `{bsn, iban, email, postcode}`.
- [ ] `find_deterministic()` is unaffected. Proved by: a test that
      `find_deterministic("<first name> van der <last name>")` returns `[]`.
- [ ] The PII eval's deterministic layer and the dataset column validation are
      unaffected. Proved by: the existing `tests/test_eval_pii.py` and the
      dataset tests pass unchanged, and a test that
      `eval.pii.deterministic_entities` returns nothing for a particle name.

## 4. Measured
- [ ] Run the PII eval on the generated evaluation corpus before and after
      (`python scripts/eval/generate_ground_truth.py /tmp/gt --count 500`, then
      `python -m wordsworth.eval.pii_run /tmp/gt/gold.jsonl` with the
      `openanonymiser` layer) and record the PERSON numbers with the date in
      `docs/reference/evaluation.md`. Proved by: the section holds both numbers
      and the date. If the service is unreachable the run fails hard; record
      that instead of a number, never an estimate.

## 5. Docs (must change with the code)
- [ ] `docs/reference/evaluation.md`: state that names with a Dutch particle are
      detected as one `PERSON` by the `dutch_particle_name` rule, anchored on a
      first-name gazetteer, that institution names are excluded, and that the
      `deterministic` layer of `pii_run` is unaffected by design. Proved by: the
      section exists and names the test file.
- [ ] `docs/how-to/detection-lists.md`: describe the first-name gazetteer (file,
      `{naam, reden}` form, refusal of an entry without reason, how to add a
      name) and note that a miss of this shape is fixed by adding the first
      name to the gazetteer, not by `deny.json`. Proved by: the section exists
      and names the file.

## 6. Check
- [ ] `openspec validate detect-dutch-particle-names --strict` passes.
- [ ] `uvx ruff check src/ tests/` and the full test suite pass; skipped
      database tests are listed in the report.
