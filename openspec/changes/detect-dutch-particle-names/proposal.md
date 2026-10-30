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

## What changes

1. **Detection**: a first name, a Dutch particle and a last name are detected
   as ONE `PERSON` span. The particle list is fixed in this change: `van`,
   `de`, `ter`, `ten`, `van der`.
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
   design stays gazetteer-anchored.
7. **An honest measurement.** The PII measurement is labelled as circular where
   the gold names come from `eval/synthetic.py`, and recall is also reported on
   a gold set not derived from the gazetteer's own first names.
8. **Aggregates tested for the double count** (see the open question below);
   replacement itself stays unchanged.
9. **Docs** that describe the behaviour change with it.

## Open questions

- **Double count in the per-layer aggregates.** Either the audit aggregate is
  deduplicated so the shorter span (the bare first name) is absorbed into the
  longer one, or the overcount is stated in the spec and tested. Which of the
  two is not decided. Either way replacement is unchanged, and `tasks.md` has a
  test that pins whichever is chosen.

- **The initial gazetteer entries.** The mechanism and the rule that each entry
  has a reason are decided; which first names the list starts with, and from
  what source, is not. The build needs a starting list to prove the scenarios;
  its coverage decides how many real names this misses, which the PII
  measurement in `tasks.md` reports.
- **Particles beyond the five** (`van den`, `van de`, `von`, `op de`, ...) are
  not in this change. Adding one is a later change to the fixed list.
- **Re-running the affected document and the corpus.** Re-anonymising document
  `1c87f856` and the count-only check on its anonymised text need the
  deployed corpus; they are an operator step, not a build task, and are not in
  `tasks.md`. Whether the rest of the corpus is reprocessed (`POST /reprocess`,
  hours of work) is likewise not decided. Updating the pilot report with the
  result of that re-check waits for it.

## Impact

- Specs: `anonymization` (ADDED, four requirements).
- Code: a new module for the particle rule and its gazetteer loader (not
  `src/wordsworth/detectors.py`'s `DETECTORS`); a gazetteer data file; new
  tests, including the gazetteer brake. The aggregate in
  `src/wordsworth/pseudonymizer.py` changes only if the dedupe option is chosen.
- Docs: `docs/reference/evaluation.md` and `docs/how-to/detection-lists.md`.
