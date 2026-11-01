# Detect names with a Dutch particle as one PERSON

## Why

The orchestrator, from the odin coding session: *"the pilot report's PII read
(wordsworth #284) found one detection miss in the Gooise Meren dossier: document
1c87f856 has a full name in clear in the anonymised output, shaped '<first name>
ter <last name>' (a Dutch particle), most likely an official in a meeting
agenda. No email addresses, phone numbers, IBANs, BSNs or title-plus-name
survived in the 15-document sample."*

Dutch surnames often carry a particle between first and last name (`van`, `de`,
`ter`, `ten`, `van der`, ...). The pilot report records the miss as a count and
a shape, not as a value (`docs/explanation/pilot-report-gooise-meren-2022.md`,
section 4). A full name left readable in an anonymised document breaks the
promise of the `anonymization` capability, and it is the one leftover the pilot
sample found.

The architect's review (wordsworth#285) found that the first version of this
change had no answer to the obvious failure of the rule: `<capitalised word>
van <capitalised word>` is also `Raad van State`, `Kamer van Koophandel`,
`Ministerie van Binnenlandse Zaken`, `Vereniging van Eigenaren` and
`Hoogheemraadschap van Rijnland`. Government documents are full of them, so a
rule without a precision anchor trades one miss for thousands of false
positives. It also did not say where the rule lives relative to
`detectors.DETECTORS`, which the PII eval and the dataset column validation read
through `find_deterministic()`.

A second architect review (wordsworth#285) of the amended change found three
more gaps, folded in below:

- The planned measurement is circular: the gold names of the evaluation corpus
  come from `eval/synthetic.py:18-21`, and a gazetteer built from the same first
  names would score itself.
- Per-layer aggregates count one person twice when GLiNER returns the bare first
  name next to the full-name span (`winner` in `pseudonymizer.py:251-256` is
  keyed by text).
- The gazetteer has no brake. A first name that is also a common capitalised
  word at sentence start (`Ton`, `Wil`, `Bart`) turns ordinary text into a
  `PERSON`, and `tests/test_allow_list_veiligheid.py` shows the pattern for
  stopping that.

A fifth architect review (wordsworth#285) found four points, folded into
`tasks.md` and the brake requirement:

- **The non-corpus brake could not be implemented as written.** "Entry as a
  sentence-initial capital" is not the shape the rule matches. The sentences now
  put each entry in the shape entry + particle + surname with a stated
  expectation per sentence, so the brake can be satisfied and cannot pass
  vacuously.
- **The second PERSON number** is reported as full-pipeline PERSON recall with
  the `per_layer` breakdown, not as the `dutch_particle_name` layer alone, which
  is near zero by construction when the gazetteer is seeded from
  `eval/synthetic.py` `VOORNAMEN`.
- **The corpus brake** asserts that each shipped entry actually occurred in the
  generated corpus, not only that no false `PERSON` appeared.
- **Tests assert on the full-name substring** in the anonymised output, never on
  the bare particle string being absent: replacement is by value.

A fourth architect review (wordsworth#285) failed the amended change on four
points, settled below:

- **The measurement could not see the rule.** `eval/pii_run.py` has two layers,
  `deterministic` and `openanonymiser`; neither runs `dutch_particle_name`, so
  a before/after PERSON number would be identical by construction.
- **The dedupe had no home.** `pseudonymizer.py` is already 507 lines.
- **The brake only looked at corpus text.** The corpus is generated from the
  same names; it cannot show that an entry misfires on ordinary Dutch.
- **Recall was left implicit.** Nothing said that the change does not close the
  Gooise Meren miss.

## What changes

1. **Detection**: a first name, a Dutch particle and a last name are detected
   as ONE `PERSON` span. The particle list is fixed in this change: `van`,
   `van der`, `van den`, `de`, `ter`, `ten`, with a test per particle.
2. **Mechanism**: the rule is its own deterministic pattern in a new module.
   It does not widen spans the entity layer already found, and it is not a row
   in `detectors.DETECTORS`. Its detections carry the layer name
   `dutch_particle_name`.
3. **Precision anchor**: a first-name gazetteer. The pattern only matches when
   the word before the particle is a gazetteer entry, so `Raad van State`,
   `Kamer van Koophandel`, `Ministerie van Binnenlandse Zaken`, `Vereniging van
   Eigenaren` and `Hoogheemraadschap van Rijnland` are not names. Every entry
   carries a reason, as entries in `allow.json` do
   (`docs/how-to/detection-lists.md`); the loader refuses an entry without one.
4. **Outside `DETECTORS`**: `find_deterministic()`, the PII eval's deterministic
   layer and the dataset column validation behave exactly as before. A
   requirement and tests pin that.
5. **Tests** with synthetic examples, one per particle, plus the negative cases.
6. **A brake on the gazetteer**, like `tests/test_allow_list_veiligheid.py`:
   every gazetteer entry is tested against the evaluation corpus, and first
   names that are also common capitalised words at sentence start (`Ton`, `Wil`,
   `Bart`) are excluded. `eval/overdetection_run.py` runs as a task and its
   result is recorded. The rule stays out of `detectors.DETECTORS` and the
   design stays gazetteer-anchored. The brake also takes non-corpus input:
   every gazetteer entry is run over a fixed set of ordinary Dutch sentences
   with a sentence-initial capital. This proves that no `Ton`-shaped entry
   misfires on those sentences; it does not prove coverage, and the docs say so.
7. **An honest measurement that can see the rule.** `dutch_particle_name` is
   added as an explicit, opt-in layer of `eval/pii_run.py` (and of
   `eval/overdetection_run.py`). Without it, the two measurement tasks would
   give the same numbers before and after. The default layers stay as they are.
   The PII measurement is labelled as circular where the gold names come from
   `eval/synthetic.py`, and a second number is reported on a gold set not
   derived from the gazetteer's own first names.
8. **Audit aggregate deduplicated, in its own module.** When a shorter span (the
   bare first name) lies inside a longer one (the full name), the shorter is
   absorbed into the longer in the per-layer aggregate, so a person is counted
   once. The logic is a pure helper module (≤200 lines) outside
   `pseudonymizer.py`, which only calls it; `pseudonymizer.py` is not split.
   Replacement itself stays unchanged. A test pins it.
9. **Recall is unknown, and the change says so.** This change builds the
   mechanism. It does not close the Gooise Meren miss: whether document
   `1c87f856`'s name is caught depends on a gazetteer that is still open (see
   open questions) and nothing here re-runs that document. The measurement file
   states recall as unknown.
10. **Scoped to the reversible driver.** The rule runs in the reversible
   anonymiser path. The irreversible `OpenAnonymiserAnonymizer` is out of scope.
11. **`Ton` and `Bart` stay unmatched, on purpose.** The docs and a required
    test state this as a known, accepted miss (about 2 of 14 seeded names).
12. **Docs** that describe the behaviour change with it.

A third architect review (wordsworth#285) found three more points, settled here:

- **`lists_hash` and the gazetteer.** The gazetteer file is not part of
  `lists_hash`, so a change to the gazetteer does not make a document look
  outdated. This is decided, not an oversight (see design).
- **Which driver.** The irreversible `OpenAnonymiserAnonymizer` (built in
  `serve.py:59-66` when `reversible_mode` is off) does not run the rule. The
  Gooise Meren pilot corpus runs in reversible mode, so that is where the miss
  was found and where the rule applies. The requirement is no longer
  driver-neutral.
- **`Ton` and `Bart` are a precision trade.** Both are seeded first names in
  `eval/synthetic.py:18-21` and both are excluded from the gazetteer, so about 2
  of the 14 seeded names stay unmatched. That is a known, accepted miss.

## Scope

This change is part (a) only: the gazetteer-anchored rule with a test per
particle. Re-anonymising the affected document (`1c87f856`) with a count-only
check is dropped from this change. It was part (b) of the split the breaker
asked for and is not decided here.

## Open questions

- **The initial gazetteer entries.** The mechanism and the rule that each entry
  has a reason are decided; which first names the list starts with, and from
  what source, is not. The build needs a starting list to prove the scenarios;
  its coverage decides how many real names this misses. That coverage is
  unknown: the measurements in `tasks.md` report what they measured and state
  recall on real documents as unknown.
- **Particles beyond the six** (`van de`, `von`, `op de`, ...) are not in this
  change. Adding one is a later change to the fixed list.
- **Re-anonymising the affected document and the corpus** is not in this
  change (see Scope). Whether and how it happens, and whether the pilot report
  is updated afterwards, is open and belongs to a separate change. The
  follow-up `reanonymise-particle-name-documents` owns gazetteer versioning
  for its `only_outdated` selection, since the gazetteer is not in
  `lists_hash`.

## Impact

- Specs: `anonymization` (ADDED, five requirements; the first is scoped to the reversible
  driver).
- Code: a new module for the particle rule and its gazetteer loader (not
  `src/wordsworth/detectors.py`'s `DETECTORS`); a gazetteer data file; new
  tests, including the gazetteer brake and its ordinary-sentence fixture; a pure
  dedupe helper module (≤200 lines) that `src/wordsworth/pseudonymizer.py` calls
  to absorb a shorter span into a longer one; the `dutch_particle_name` layer in
  `src/wordsworth/eval/pii_run.py` and `overdetection_run.py`.
- Docs: `docs/reference/evaluation.md` and `docs/how-to/detection-lists.md`.
