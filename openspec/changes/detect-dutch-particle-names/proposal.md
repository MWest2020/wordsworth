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

1. **Detection**: a first name, a Dutch particle (one or more words: `van`,
   `de`, `ter`, `ten`, `van der`, ...) and a last name are detected as ONE
   `PERSON` span.
2. **A precision anchor**: the rule SHALL NOT match institution names. The
   spec carries negative scenarios for `Raad van State`, `Kamer van
   Koophandel`, `Ministerie van Binnenlandse Zaken`, `Vereniging van Eigenaren`
   and `Hoogheemraadschap van Rijnland`.
3. **Outside `DETECTORS`**: the rule is NOT a row in `detectors.DETECTORS`, so
   `find_deterministic()`, the PII eval's deterministic layer and the dataset
   column validation behave exactly as before. A second requirement and tests
   pin that.
4. **Tests** with synthetic examples, one per particle, plus the negative cases.
5. **Docs** that describe the behaviour change with it.

## Open questions

- **Mechanism.** Not decided in the channel: whether the span is widened from
  what the entity layer already finds or found by its own pattern. The apply
  step chooses. Whatever it chooses must be deterministic, must live outside
  `detectors.DETECTORS`, and must satisfy the negative scenarios.
- **First-name gazetteer.** Whether the precision anchor is a list of known
  first names is not decided. If one is chosen, every entry carries a reason, as
  entries in `allow.json` do (`docs/how-to/detection-lists.md`): the loader
  refuses an entry without one, and a bare list of names that nobody can review
  is not accepted. This is a constraint on that option, not a requirement of
  this change.
- **Which particles are in the list.** The channel named `van`, `de`, `ter`,
  `ten`, `van der` and "...". The full list is not fixed here; the spec and
  tests cover the five named.
- **Re-running the affected document and the corpus.** Re-anonymising document
  `1c87f856` and the count-only check on its anonymised text need the
  deployed corpus; they are an operator step, not a build task, and are not in
  `tasks.md`. Whether the rest of the corpus is reprocessed (`POST /reprocess`,
  hours of work) is likewise not decided. Updating the pilot report with the
  result of that re-check waits for it.

## Impact

- Specs: `anonymization` (ADDED, two requirements).
- Code: the PERSON detection step (not `src/wordsworth/detectors.py`'s
  `DETECTORS`); new tests.
- Docs: `docs/reference/evaluation.md` and `docs/how-to/detection-lists.md`.
