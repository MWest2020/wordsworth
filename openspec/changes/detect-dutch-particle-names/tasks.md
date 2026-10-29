# Tasks

## 1. Detection
- [ ] Detect `<first name> <particle> <last name>` as one `PERSON` span in the
      entity (PERSON) step, for the particles `van`, `de`, `ter`, `ten` and
      `van der`. Proved by: a new test file `tests/test_particle_names.py` with
      synthetic names, one example per particle, asserting one `PERSON`
      detection covering the whole name.
- [ ] No part of the name stays readable. Proved by: a test in the same file
      that runs `ReversibleAnonymizer.anonymize` on a text with such a name
      and asserts neither first name, particle nor last name is in the output.
- [ ] Ordinary text is not swallowed. Proved by: a test that a sentence with
      lowercase `de`/`van` between ordinary words yields no `PERSON`.
- [ ] Institutions are not names. Proved by: a parametrised test over `Raad van
      State`, `Kamer van Koophandel`, `Ministerie van Binnenlandse Zaken`,
      `Vereniging van Eigenaren` and `Hoogheemraadschap van Rijnland`, each in
      a sentence, asserting no `PERSON` is produced from them.

## 2. Outside the deterministic table
- [ ] Add no row to `detectors.DETECTORS`. Proved by: a test asserting the set of
      labels in `DETECTORS` is still `{bsn, iban, email, postcode}`.
- [ ] `find_deterministic()` is unaffected. Proved by: a test that
      `find_deterministic("<first name> van der <last name>")` returns `[]`.
- [ ] The PII eval's deterministic layer and the dataset column validation are
      unaffected. Proved by: the existing `tests/test_eval_pii.py` and the
      dataset tests pass unchanged, and a test that
      `eval.pii.deterministic_entities` returns nothing for a particle name.

## 3. Measured
- [ ] Run the PII eval on the generated evaluation corpus before and after
      (`python scripts/eval/generate_ground_truth.py /tmp/gt --count 500`, then
      `python -m wordsworth.eval.pii_run /tmp/gt/gold.jsonl` with the
      `openanonymiser` layer) and record the PERSON numbers with the date in
      `docs/reference/evaluation.md`. Proved by: the section holds both numbers
      and the date. If the service is unreachable the run fails hard; record
      that instead of a number, never an estimate.

## 4. Docs (must change with the code)
- [ ] `docs/reference/evaluation.md`: state that names with a Dutch particle are
      detected as one `PERSON` in the entity step, that institution names are
      excluded, and that the `deterministic` layer of `pii_run` is unaffected
      by design. Proved by: the section exists and names the test file.
- [ ] `docs/how-to/detection-lists.md`: add a short note that the particle rule
      is code, not a list entry, and that a miss of this shape is fixed by the
      rule, not by `deny.json`. Proved by: the note exists.

## 5. Check
- [ ] `openspec validate detect-dutch-particle-names --strict` passes.
- [ ] `uvx ruff check src/ tests/` and the full test suite pass; skipped
      database tests are listed in the report.
