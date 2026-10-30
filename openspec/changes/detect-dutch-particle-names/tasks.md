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

- [ ] A brake on the gazetteer. Proved by: a new test (e.g.
      `tests/test_particle_names_veiligheid.py`, modelled on
      `tests/test_allow_list_veiligheid.py`) that runs every shipped gazetteer
      entry against the evaluation corpus and fails when an entry produces a
      `PERSON` from ordinary text.
- [ ] First names that are also common capitalised words at sentence start
      (`Ton`, `Wil`, `Bart`) are excluded. Proved by: a test that the shipped
      gazetteer holds none of them, and that `Ton van der <last name>` at
      sentence start with a word like `Ton` yields no `PERSON`.
- [ ] Run `python -m wordsworth.eval.overdetection_run gold.jsonl --out
      meting-overdetectie-<nn>.md` with the gazetteer rule in place and record
      the result in `docs/explanation/` with the date. Proved by: the
      measurement file exists and holds the result. If OpenAnonymiser is
      unreachable the run reports "not run"; record that, never an estimate.

## 3. Outside the deterministic table
- [ ] Add no row to `detectors.DETECTORS`. Proved by: a test asserting the set of
      labels in `DETECTORS` is still `{bsn, iban, email, postcode}`.
- [ ] `find_deterministic()` is unaffected. Proved by: a test that
      `find_deterministic("<first name> van der <last name>")` returns `[]`.
- [ ] The PII eval's deterministic layer and the dataset column validation are
      unaffected. Proved by: the existing `tests/test_eval_pii.py` and the
      dataset tests pass unchanged, and a test that
      `eval.pii.deterministic_entities` returns nothing for a particle name.

## 4. Aggregates

- [ ] Per-layer aggregates and the bare first name. `winner` in
      `src/wordsworth/pseudonymizer.py:251-256` is keyed by text, so a person is
      counted twice when GLiNER returns the bare first name next to the
      full-name span. Either dedupe the audit aggregate so the shorter span is
      absorbed into the longer one, or state the overcount in the spec and test
      it (the choice is an open question in the proposal). Replacement stays
      unchanged. Proved by: a test with a text where a stub entity layer returns
      the bare first name and the full name, asserting the aggregate counts for
      that person (one, or the stated overcount), and that the anonymised output
      is identical either way.

## 5. Measured
- [ ] Run the PII eval on the generated evaluation corpus before and after
      (`python scripts/eval/generate_ground_truth.py /tmp/gt --count 500`, then
      `python -m wordsworth.eval.pii_run /tmp/gt/gold.jsonl` with the
      `openanonymiser` layer) and record the PERSON numbers with the date in
      `docs/reference/evaluation.md`. Proved by: the section holds both numbers
      and the date. If the service is unreachable the run fails hard; record
      that instead of a number, never an estimate.
- [ ] Label the measurement as circular. The gold names come from
      `eval/synthetic.py:18-21`, the same first names a gazetteer would be
      seeded from. Proved by: `docs/reference/evaluation.md` says so next to the
      numbers.
- [ ] Report recall on a gold set not derived from the gazetteer's own first
      names. Proved by: `docs/reference/evaluation.md` holds a second PERSON
      recall number with the date, on names whose first names are not in the
      shipped gazetteer's source, and says how that set was built.

## 6. Docs (must change with the code)
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
- [ ] `docs/how-to/detection-lists.md` and `docs/reference/evaluation.md` also state
      the gazetteer brake (every entry tested against the corpus; `Ton`, `Wil`,
      `Bart` excluded). Proved by: the section exists and names the test file.

## 7. Check
- [ ] `openspec validate detect-dutch-particle-names --strict` passes.
- [ ] `uvx ruff check src/ tests/` and the full test suite pass; skipped
      database tests are listed in the report.
