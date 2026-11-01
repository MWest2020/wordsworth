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
- **The brake takes non-corpus input.** The evaluation corpus is generated from
  the same names a gazetteer would be seeded from, so it cannot show that an
  entry misfires on ordinary Dutch. Besides the corpus, every gazetteer entry is
  run over a fixed set of Dutch sentences, kept in a fixture file, each with the
  entry in the shape the rule matches (entry + particle + capitalised surname)
  and a stated expectation per sentence. A "sentence-initial capital" alone is
  not that shape, so the rule could never fire and the check would pass
  vacuously; and "no `PERSON`" for an entry in the matching shape is
  unsatisfiable. The set holds at least one sentence per particle that expects
  a `PERSON`, and the test guards that those detections occur. What this proves
  is narrow and the docs say so: the rule is exercised on every entry and no
  `Ton`-shaped entry is shipped (that exclusion is its own check). It is not
  coverage: a word that misfires in a sentence nobody wrote down passes.
- **The corpus brake asserts occurrence.** For each shipped entry the test
  asserts that the entry occurred in the generated corpus before a particle and
  last name, before it asserts that no false `PERSON` came from it. Otherwise
  an entry the generator never emits passes vacuously.
- **Tests assert on the full name.** Replacement is by value, so an unrelated
  `van` or `de` legitimately survives in the output. Tests assert that the
  full-name substring is absent, never that the bare particle string is.
- **The second PERSON number is full-pipeline recall.** With the gazetteer
  seeded from `eval/synthetic.py` `VOORNAMEN`, the `dutch_particle_name` layer
  alone is near zero on a gold set with other first names, which is identical
  by construction again. The number is full-pipeline PERSON recall with the
  `per_layer` breakdown.
- **The measurement can see the rule.** `eval/pii_run.py` offers only the layers
  `deterministic` and `openanonymiser`; neither runs `dutch_particle_name`, so a
  before/after run over them gives the same number by construction. The rule is
  added as an explicit third layer, `dutch_particle_name`, in `pii_run._LAYERS`
  and in `overdetection_run.py`. It is opt-in: the default layers stay
  `deterministic,openanonymiser`, so "before" is the default run and "after" is
  the run with `dutch_particle_name` added, and the deterministic layer is still
  unchanged. (Running the measurement through `ReversibleAnonymizer` instead was
  considered and rejected: it mixes the rule with replacement and tokens, and
  the PII eval scores detections, not output text.)
- **The measurement says what it is.** The gold names of the generated corpus
  come from `eval/synthetic.py:18-21`; a gazetteer seeded from the same first
  names scores itself. The result is labelled circular in
  `docs/reference/evaluation.md`, and a second PERSON number is reported on a
  gold set not derived from the gazetteer's own first names.
- **Recall is unknown.** This change builds the mechanism; it does not close the
  Gooise Meren miss. Neither number measures recall on real government
  documents: the circular one scores itself, the second one measures a
  constructed set. The measurement file says plainly that recall on the real
  corpus is unknown, and no document says the miss is fixed.
- **The audit aggregate is deduplicated.** `winner` in
  `pseudonymizer.py:251-256` is keyed by text, so when GLiNER returns the bare
  first name next to the full-name span the per-layer aggregate counts one
  person twice. The aggregate absorbs the shorter span into the longer one, so
  the person is counted once. Only the aggregate changes; what is replaced is
  not touched. (Stating and testing the overcount instead was considered and
  rejected: an audit count that says two people for one is wrong.)
- **The dedupe is a pure helper module.** `pseudonymizer.py` has 507 lines
  against the ≤200 rule. The dedupe goes into its own module (e.g.
  `src/wordsworth/audit_dedupe.py`, ≤200 lines) as a pure function over the
  entity list; `pseudonymizer.py` only calls it. `pseudonymizer.py` is not split
  in this change: that is a refactor of its own, and mixing it in would hide the
  dedupe in a large diff.
- **The gazetteer file stays out of `lists_hash`.** `lists_hash` fingerprints
  the allow/deny lists recorded on a document, and `reprocess.outdated`
  compares it. Changing the gazetteer therefore does not mark any document
  outdated. That is chosen: folding the gazetteer in would flag the whole
  corpus outdated on every added name. Versioning the gazetteer for the
  `only_outdated` selection belongs to the follow-up
  `reanonymise-particle-name-documents`, not to this change.
- **Scoped to the reversible driver.** The rule runs in the reversible
  anonymiser path. The irreversible `OpenAnonymiserAnonymizer`, which
  `serve.py:59-66` builds when `reversible_mode` is off, is explicitly out of
  scope: the Gooise Meren pilot corpus runs in reversible mode, and that is
  where the miss was found. The spec says so; it is not driver-neutral. A
  deployment without `reversible_mode` does not get the rule from this change.
- **`Ton` and `Bart` are a deliberate precision trade.** Both are seeded
  first names in `eval/synthetic.py:18-21` and both are common capitalised
  words at sentence start, so they are excluded and about 2 of the 14 seeded
  names stay unmatched. This is a known, accepted miss, stated in the docs and
  pinned by a test, not an oversight. The rule stays out of
  `detectors.DETECTORS`.
- **Scope: part (a) only.** Re-anonymising document `1c87f856` with a
  count-only check is not part of this change.
- **Fixed particle list.** `van`, `van der`, `van den`, `de`, `ter`, `ten`. A
  particle of two words is one particle. Further particles are a later change.
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
- **Folding the gazetteer into `lists_hash`.** It would mark every document
  outdated on each added name; versioning is the follow-up's job.
- **A driver-neutral requirement.** The irreversible driver is not wired for
  this rule here; claiming it would promise what the change does not build.
- **Splitting `pseudonymizer.py` in this change.** Out of scope; the dedupe only
  needs a place outside it.
- **Measuring with the existing layers only.** Identical before and after by
  construction; it would report an instrument, not the rule.
- **A brake on corpus text only.** The corpus shares its names with the
  gazetteer; it cannot show an entry misfiring on ordinary sentences.
- **Keeping `Ton` and `Bart` for recall.** They turn ordinary sentence starts
  into a `PERSON`; the miss is accepted instead.

## Left open

The initial gazetteer entries and their source, particles beyond the six, and
re-anonymisation of the affected document: see the proposal's open questions.
They are not requirements.
