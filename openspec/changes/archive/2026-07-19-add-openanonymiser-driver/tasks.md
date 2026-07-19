# Tasks — add-openanonymiser-driver

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.
UNBLOCKED (2026-07-19): use the fork `MWest2020/OpenAnonymiser_light` (package
`OpenAnonymizer`); see proposal Impact for the git-dep + uv-sources pitfalls.

## 1. Driver
- [x] 1.1 `openanonymiser_driver.py`: `OpenAnonymiserAnonymizer` implementing the
      `Anonymizer` protocol, delegating to OpenAnonymiser; irreversible; local
- [x] 1.2 Compose with the deterministic detectors (structured-PII precision) then
      OpenAnonymiser entities; merge counts per type
- [x] 1.3 Failure raises — never emit un-redacted text

## 2. Tests
- [x] 2.1 Satisfies `Anonymizer` protocol; injectable into `process()`
- [x] 2.2 A personal name is redacted; structured PII still redacted
- [x] 2.3 Engine failure raises (no clear-text leak)
