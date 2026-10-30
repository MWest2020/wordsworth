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
6. **Docs** that describe the behaviour change with it.

## Open questions

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

- Specs: `anonymization` (ADDED, three requirements).
- Code: a new module for the particle rule and its gazetteer loader (not
  `src/wordsworth/detectors.py`'s `DETECTORS`); a gazetteer data file; new
  tests.
- Docs: `docs/reference/evaluation.md` and `docs/how-to/detection-lists.md`.
