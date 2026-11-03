# Tasks

Step 1 of 4, split from `detect-dutch-particle-names` (#285). Build this first.

## 1. Rule and gazetteer
- [x] `src/wordsworth/data/voornamen.json` with the 12 entries named in
      design.md, each `{"naam", "reden"}`, and a loader in
      `src/wordsworth/particle_names.py` that reads it via
      `importlib.resources`, refuses an entry with a missing or blank `reden`
      (naming the entry) and raises when the file is missing. Proved by: tests
      in `tests/test_particle_names.py` for the refusal, for a missing file
      (point the loader at a non-existent path), and that every shipped entry
      has a non-empty `reden` and the file loads through `importlib.resources`.
- [x] The pattern in `src/wordsworth/particle_names.py` (≤200 lines): gazetteer
      first name, particle (`van`, `van der`, `van den`, `de`, `ter`, `ten`),
      capitalised last name, as ONE `PERSON` span, layer `dutch_particle_name`.
      Proved by: a parametrised test, one synthetic name per particle (six
      cases), asserting one `PERSON` covering the whole name with that layer.
- [x] Ordinary text is not swallowed: a sentence with lowercase `de`/`van`
      between ordinary words yields no `PERSON`. Proved by: a test.
- [x] Institutions are not names: a parametrised test over `Raad van State`,
      `Kamer van Koophandel`, `Ministerie van Binnenlandse Zaken`, `Vereniging
      van Eigenaren` and `Hoogheemraadschap van Rijnland`, each in a sentence,
      asserting no `PERSON`.
- [x] The anchor is the gazetteer: `<unlisted word> van <Word>` yields no
      `PERSON` and the same shape with a listed first name does. Proved by: a
      test.
- [x] `Ton`, `Wil` and `Bart` are not entries, and `Ton van der <Last>` /
      `Bart de <Last>` yield no `PERSON` from this rule; over the 14 `VOORNAMEN`
      of `eval/synthetic.py`, exactly `Ton` and `Bart` stay unmatched. Proved
      by: a test asserting them by name, with a comment that this is the
      accepted precision trade.
- [x] The gazetteer stays out of `lists_hash`: the hash is identical with two
      different gazetteer contents. Proved by: a test.

## 2. Wiring
- [x] `ReversibleAnonymizer.anonymize` adds the rule's detections to the
      entity layer's before `self._lists.apply`. Proved by: a test that runs it
      (stub detection seam returning nothing) on a text with such a name and
      asserts the full-name substring is absent from the output, with an
      unrelated lowercase `van` elsewhere that may remain; and that the
      per-layer aggregate holds a `dutch_particle_name` entry with a count and
      no value or offset.
- [x] `pseudonymizer.py` grows by the call only. Proved by: the diff.
- [x] The irreversible driver is out of scope: `OpenAnonymiserAnonymizer`
      with a stub client yields no `dutch_particle_name` detection. Proved by: a
      test.

## 3. Outside the deterministic table
- [x] `detectors.DETECTORS` labels are still `{bsn, iban, email, postcode}`;
      `find_deterministic("<first name> van der <last name>")` returns `[]`;
      `eval.pii.deterministic_entities` returns nothing for a particle name.
      Proved by: tests, and the existing `tests/test_eval_pii.py` and dataset
      tests pass unchanged.

## 4. Docs
- [x] `docs/how-to/detection-lists.md`: the gazetteer (file, `{naam, reden}`,
      refusal without a reason, how to add a name, that a miss of this shape is
      fixed by adding the first name here and not by `deny.json`, that an allow
      rule on `PERSON` can suppress a particle name, reversible mode only, not
      in `lists_hash`, `Ton`/`Bart` excluded on purpose). Proved by: the
      section exists and names `tests/test_particle_names.py`.

## 5. Check
- [x] `openspec validate particle-names-rule --strict` passes.
- [x] `uv run ruff check src/ tests/` is clean and the full test suite passes;
      skipped database tests are listed in the report.
