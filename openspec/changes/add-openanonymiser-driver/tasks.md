# Tasks — add-openanonymiser-driver

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.
BLOCKED until OpenAnonymiser is reachable from the build environment (Mark).

## 1. Driver
- [ ] 1.1 `openanonymiser_driver.py`: `OpenAnonymiserAnonymizer` implementing the
      `Anonymizer` protocol, delegating to OpenAnonymiser; irreversible; local
- [ ] 1.2 Compose with the deterministic detectors first (structured-PII
      precision) then OpenAnonymiser entities; deterministic types (BSN/IBAN/
      email) are authoritative — ignore OpenAnonymiser detections of those types;
      preserve the opaque `[LABEL]` placeholders; merge counts disjointly per type
- [ ] 1.3 Failure raises — never emit un-redacted text
- [ ] 1.4 Verify the GLiNER model licence is EUPL-compatible before shipping

## 2. Tests
- [ ] 2.1 Satisfies `Anonymizer` protocol; injectable into `process()`
- [ ] 2.2 A personal name is redacted; structured PII still redacted
- [ ] 2.3 Structured PII is NOT double-counted or double-replaced by the composite
      (deterministic types authoritative; placeholders preserved)
- [ ] 2.4 Engine failure raises (no clear-text leak)
