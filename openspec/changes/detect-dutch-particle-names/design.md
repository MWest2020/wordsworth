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
  lives in the entity (PERSON) step instead, and the following stay as they are:
  `DETECTORS` keeps its four labels, `find_deterministic()` returns no hit for a
  name with a particle, and the PII eval's deterministic layer and the dataset
  column validation give the same results as before. Tests pin each.
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
  generalise to `Waterschap van ...` or `Stichting van ...`. The apply step
  chooses the anchor (see the proposal) and the scenarios are the acceptance.

## Left open

Mechanism, the first-name gazetteer and the full particle list: see the
proposal's open questions. They are not requirements. If a gazetteer is
chosen, each entry carries a reason, in the form `allow.json` uses
(`{"patroon"/name, "reden"}`), refused at load when missing.
