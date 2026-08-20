## Why

Reversible pseudonymisation only covered the deterministic detectors (BSN/IBAN/
email); GLiNER-detected entities — personal names, locations — still went through
the irreversible `<PERSON>` replace path. Names are the dominant PII in these
documents, so without reversible entities the straat cannot run in a mode where
every PII value is later revealable by whoever holds its type's key. Fase B needs
the whole pipeline reversible while the index still holds only pseudonyms.

## What Changes

- **`ReversibleAnonymizer`** (`Anonymizer` driver): runs the deterministic keyed
  pass (reusing `Pseudonymizer`), then detects GLiNER entities via a detection
  seam and replaces each span with a `[TYPE:hash]` keyed token under that type's
  per-type key, storing the encrypted original in the mapping store. All PII —
  deterministic and entity — becomes reversible keyed pseudonyms; the index sees
  only pseudonyms.
- **Detection seam** `DetectFn = (text) -> list[Entity]`. The default engine
  (`detect_entities`) calls OpenAnonymiser, reusing the existing chunking and
  concurrency, and maps per-chunk spans back to whole-text offsets. Tests inject
  a fake, so the entity path is provable without the service.
- **Fail-hard**: a detection-engine error raises `AnonymizationEngineError`; text
  with un-pseudonymised entities is never emitted (no silent fallback).
- **Robust substitution**: only well-formed, non-overlapping spans whose slice
  still matches the detected text are applied, right-to-left so offsets stay valid.

## Capabilities

### Modified Capabilities
- `pseudonymization`: entity PII (names, locations, …) is reversibly pseudonymised
  under its per-type key alongside deterministic PII; selective, key-gated reveal
  (already built) now covers entity types too.

## Impact

- Code: `openanonymiser_driver.py` (`Entity`, `_detect_one`, `detect_entities`),
  `pseudonymizer.py` (`ReversibleAnonymizer`, `DetectFn`). No pipeline default
  change (reversible entity mode is opt-in/injectable this cycle); no schema
  change (the type is carried in the token prefix); no new dependencies.
- Tests: pure/local (fake detector: compose, per-type key, selective reveal,
  stability, fail-hard, overlap) + DB-integration (entity deanonymize + audit) in CI.
- Foundational for wiring reversible mode into the deployed straat and the reveal
  API.
