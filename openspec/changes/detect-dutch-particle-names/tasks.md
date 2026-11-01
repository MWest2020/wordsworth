# Tasks

## 1. Detection
- [ ] New module (e.g. `src/wordsworth/particle_names.py`, ≤200 lines) with a
      deterministic pattern: gazetteer first name, particle (`van`, `van der`,
      `van den`, `de`, `ter`, `ten`), capitalised last name, as ONE `PERSON`
      span, layer `dutch_particle_name`. Proved by: a new test file
      `tests/test_particle_names.py` with a parametrised test, one synthetic
      name per particle (six cases), asserting one `PERSON` detection covering
      the whole name and layer `dutch_particle_name`.
- [ ] The rule runs in anonymisation. Proved by: a test in the same file that
      runs `ReversibleAnonymizer.anonymize` on a text with such a name and
      asserts neither first name, particle nor last name is in the output.
- [ ] Scoped to the reversible driver. Proved by: a test that
      `OpenAnonymiserAnonymizer` (with a stub client) given a particle name
      yields no `dutch_particle_name` detection, so the scope is pinned rather
      than accidental.
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
- [ ] The gazetteer stays out of `lists_hash`. Proved by: a test that the
      lists hash is identical before and after the gazetteer file changes, and
      `design.md` states the choice and names
      `reanonymise-particle-name-documents` as owner of gazetteer versioning.
- [ ] `Ton` and `Bart` are a known, accepted miss. Proved by: a test over the
      `VOORNAMEN` of `eval/synthetic.py` that, with the shipped gazetteer,
      exactly `Ton` and `Bart` (2 of 14) are left unmatched before a particle
      and last name, asserted by name with a comment that this is the accepted
      precision trade.
- [ ] The brake takes non-corpus input. Add a fixture of ordinary Dutch
      sentences (e.g. `tests/fixtures/gewone_zinnen_nl.txt`), each with a slot
      for a gazetteer entry as sentence-initial capital followed by a particle
      and a capitalised word in its ordinary sense, at least one sentence per
      particle, and run every shipped entry over all of them. Proved by: a test
      in `tests/test_particle_names_veiligheid.py` that fails when any entry
      yields a `PERSON` on any sentence, plus a negative control: a test that a
      stub gazetteer holding `Ton` makes that test's check fail on the fixture.
      The test's docstring and the docs say plainly that this proves no
      `Ton`-shaped entry, not coverage.
- [ ] Run `python -m wordsworth.eval.overdetection_run gold.jsonl --out
      meting-overdetectie-<nn>.md` with the `dutch_particle_name` layer added
      (task in section 5) and record the result in `docs/explanation/` with the
      date. Proved by: the measurement file exists, holds the result, and names
      the layers it ran. If OpenAnonymiser is unreachable the run reports "not
      run"; record that, never an estimate.

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

- [ ] Dedupe the audit aggregate. `winner` in
      `src/wordsworth/pseudonymizer.py:251-256` is keyed by text, so a person is
      counted twice when GLiNER returns the bare first name next to the
      full-name span. The aggregate absorbs the shorter span into the longer
      one. Replacement stays unchanged. Proved by: a test with a text where a
      stub entity layer returns the bare first name and the full name,
      asserting the aggregate counts that person once, and that the anonymised
      output is identical to the output without the dedupe.
- [ ] The dedupe lives in a pure helper module outside `pseudonymizer.py`
      (e.g. `src/wordsworth/audit_dedupe.py`, ≤200 lines, no I/O), which
      `pseudonymizer.py` only calls. `pseudonymizer.py` is not split and does
      not grow beyond the call. Proved by: a unit test
      (`tests/test_audit_dedupe.py`) that calls the helper directly on entity
      lists (bare first name inside full name, two separate people with the
      same first name, equal spans), and a check that the new module has ≤200
      lines and that `wc -l src/wordsworth/pseudonymizer.py` is not above its
      pre-change count plus the call.

## 5. Measured
- [ ] Make the measurement able to see the rule. Add `dutch_particle_name` as
      an explicit, opt-in layer in `_LAYERS` of `src/wordsworth/eval/pii_run.py`
      and in `eval/overdetection_run.py`; the default layers stay
      `deterministic,openanonymiser`. Today neither layer runs the rule, so
      before and after would be identical by construction. Proved by: a test
      that `build_detect(["dutch_particle_name"])` returns a `PERSON` for a
      synthetic particle name, that `build_detect(["deterministic",
      "openanonymiser"])` (stub client) still returns none for it, and that the
      default of `--layers` is unchanged.
- [ ] Run the PII eval on the generated evaluation corpus before and after
      (`python scripts/eval/generate_ground_truth.py /tmp/gt --count 500`, then
      `python -m wordsworth.eval.pii_run /tmp/gt/gold.jsonl`: "before" with
      `--layers deterministic,openanonymiser`, "after" with
      `--layers deterministic,openanonymiser,dutch_particle_name`) and record
      the PERSON numbers with the date in `docs/reference/evaluation.md`.
      Proved by: the section holds both numbers, the date and the exact layers
      of each run, and the two runs differ in the layers they ran. If the
      service is unreachable the run fails hard; record that instead of a
      number, never an estimate.
- [ ] Label the measurement as circular. The gold names come from
      `eval/synthetic.py:18-21`, the same first names a gazetteer would be
      seeded from. Proved by: `docs/reference/evaluation.md` says so next to the
      numbers.
- [ ] Report PERSON recall on a gold set not derived from the gazetteer's own
      first names. Proved by: `docs/reference/evaluation.md` holds a second
      PERSON recall number with the date, on names whose first names are not in
      the shipped gazetteer's source, and says how that set was built and that
      it is a constructed set.
- [ ] State recall as unknown. The change builds the mechanism and does not
      close the Gooise Meren miss: document `1c87f856` is not re-run, and the
      gazetteer coverage is open. Proved by: the measurement file
      (`meting-overdetectie-<nn>.md`) and the `docs/reference/evaluation.md`
      section both say, in one sentence each, that recall on real documents is
      unknown and that the Gooise Meren miss is not closed by this change; a
      grep for both sentences finds them, and no doc says the miss is fixed.

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
      the gazetteer brake (every entry tested against the corpus and over the
      ordinary-sentence fixture; `Ton`, `Wil`, `Bart` excluded; the brake proves
      no `Ton`-shaped entry, not coverage). Proved by: the section exists and
      names the test file and the fixture.
- [ ] `docs/reference/evaluation.md` documents the `dutch_particle_name` layer of
      `pii_run` (opt-in, default layers unchanged, how to run before and after).
      Proved by: the section exists and names the `--layers` value.

- [ ] `docs/reference/evaluation.md` and `docs/how-to/detection-lists.md` state
      that the rule applies in reversible mode only (the irreversible
      `OpenAnonymiserAnonymizer` is out of scope), that the gazetteer is not in
      `lists_hash`, and that `Ton` and `Bart` stay unmatched on purpose (about 2
      of 14 seeded names, a known, accepted miss). Proved by: each section
      exists and names the test that pins it.

## 7. Check
- [ ] `openspec validate detect-dutch-particle-names --strict` passes.
- [ ] `uvx ruff check src/ tests/` and the full test suite pass; skipped
      database tests are listed in the report.
