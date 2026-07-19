# Design decisions — add-openanonymiser-driver

## A second driver behind the existing seam

`OpenAnonymiserAnonymizer.anonymize(text) -> AnonymizationResult` delegates to
OpenAnonymiser (Presidio + GLiNER `gliner_multi_pii-v1` + deterministic regex:
BSN elfproef, IBAN mod-97). It returns the same `(text, counts)` shape, so the
pipeline and API are unchanged — only the injected anonymizer differs.

## Composition with the deterministic driver

Options for the builder (decide at implement time): either OpenAnonymiser fully
replaces the interim driver, or a composite runs the deterministic detectors
first (guaranteed structured-PII precision) then OpenAnonymiser for entities.
Recommended: composite — keep the audited elfproef/mod-97 guarantees, add ML
entity coverage on top. Counts merged per type.

## Invariants

- **Local only** — GLiNER/Presidio on CPU (GPU via an explicit, revocable
  endpoint only if measured throughput blocks the run; never silently in the
  critical path).
- **Hard failure** — if OpenAnonymiser errors, raise; never emit un-redacted text.
- **Irreversible** — placeholders carry no mapping (pseudonymization is separate).

## Blocked-on note

OpenAnonymiser is not reachable from this build agent (org hook; not on PyPI).
This spec is ready; the build waits until Mark makes the dependency reachable
(vendor into the repo, publish under a reachable name, or grant access).
