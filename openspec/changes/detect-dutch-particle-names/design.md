# Design

## Decided

- **One span.** First name, particle and last name form ONE `PERSON` detection,
  as street and house number do for an address. Detecting the pieces separately
  leaves a readable particle and a readable half-name, or several tokens for one
  person.
- **Particles of any length.** `van der` is one particle of two words; the span
  runs from the first name to the end of the last name.
- **Precision before recall.** `<Capitalised> van <Capitalised>` is also an
  institution (`Raad van State`, `Kamer van Koophandel`, `Ministerie van
  Binnenlandse Zaken`, `Vereniging van Eigenaren`, `Hoogheemraadschap van
  Rijnland`). Those five are negative scenarios in the spec; a rule that
  redacts them makes a Woo decision unreadable without protecting anybody, the
  same argument the spec makes for `Postbus`.
- **Not a row in `detectors.DETECTORS`.** The table is shared by
  `DeterministicAnonymizer`, `Pseudonymizer`, `find_deterministic()`, the PII
  eval's deterministic layer (`eval/pii.py`) and the dataset column validation
  (`datasets.py`). Its rows are validated, high-precision values (elfproef,
  mod-97, email, postcode); a name rule is neither validated nor
  high-precision, and a row there would silently change all of those paths: the
  eval would score a name rule as a "deterministic" layer, and a dataset column
  holding company names would be classified as containing PERSON. So the rule
  lives in its own module instead, and the following stay as they are:
  `DETECTORS` keeps its four labels, `find_deterministic()` returns no hit for a
  name with a particle, and the PII eval's deterministic layer and the dataset
  column validation give the same results as before. Tests pin each.
- **Mechanism: its own pattern in a new module.** The rule finds the span
  itself (first name, particle, last name) instead of widening what the entity
  layer found. Widening depends on the entity layer having found a fragment
  first, which is exactly what failed for the Gooise Meren name, and it would
  make the result depend on a model. Its detections carry the layer name
  `dutch_particle_name`, so the per-layer aggregates show what it found.
- **Anchor: a first-name gazetteer.** The pattern matches only when the word
  before the particle is in the gazetteer. Institution words (`Raad`, `Kamer`,
  `Ministerie`, ...) are not first names, so the class of institutions is
  excluded, not just five named ones.
- **Every gazetteer entry has a reason.** An entry is `{"naam", "reden"}`; the
  loader refuses an entry without a reason, as `detection_lists.py` does for
  `allow.json`. A bare list nobody can review is not accepted.
- **A brake on the gazetteer.** Like the allow-list brake
  (`tests/test_allow_list_veiligheid.py`), every gazetteer entry is tested
  against the evaluation corpus, so "this entry turns ordinary text into a
  person" is established before roll-out rather than trusted. First names that
  are also common capitalised words at sentence start (`Ton`, `Wil`, `Bart`) are
  excluded from the gazetteer. `eval/overdetection_run.py` runs as a task and
  its result is recorded. The gazetteer-anchored design is unchanged.
- **The measurement says what it is.** The gold names of the generated corpus
  come from `eval/synthetic.py:18-21`; a gazetteer seeded from the same first
  names scores itself. The result is labelled circular in
  `docs/reference/evaluation.md`, and recall is also reported on a gold set not
  derived from the gazetteer's own first names.
- **Replacement stays unchanged.** `winner` in `pseudonymizer.py:251-256` is keyed
  by text, so when GLiNER returns the bare first name next to the full-name span
  the per-layer aggregate counts one person twice. Only the aggregate is at
  stake; what is replaced is not touched.
- **Fixed particle list.** `van`, `de`, `ter`, `ten`, `van der`. A particle of
  two words is one particle. Further particles are a later change.
- **Proof by shape, not by value.** The tests use synthetic names, one example
  per particle.

## Rejected

- **Allow/deny list entries for this name.** A deny rule for one name fixes the
  one document and nothing of the shape; lists are for exceptions, not for a
  detection gap.
- **Redacting every capitalised word pair.** It would swallow ordinary text
  (see the over-detection work in `redaction-overdetection`).
- **A new row in `detectors.DETECTORS`.** See above: it would change
  `find_deterministic()` and everything built on it without anyone choosing to.
- **An institution deny-list as the only precision measure.** Five named
  institutions are scenarios, not the whole class; a list of them alone does not
  generalise to `Waterschap van ...` or `Stichting van ...`.
- **Widening the spans the entity layer finds.** See Mechanism above.

## Left open

The initial gazetteer entries and their source, particles beyond the five, and
whether the double count in the aggregates is deduplicated or stated and tested:
see the proposal's open questions. They are not requirements.
