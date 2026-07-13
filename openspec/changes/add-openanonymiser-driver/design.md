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
entity coverage on top.

The composite MUST resolve the overlap between the two engines (Presidio also
recognises email/IBAN — the same types the deterministic pass owns):

- **Deterministic types are authoritative.** For the types the deterministic
  driver handles (BSN, IBAN, email), its result wins; any OpenAnonymiser
  detection of those same types is ignored, so an entity is never counted or
  replaced twice (no `[[EMAIL]]`, no inflated counts).
- **Placeholders are preserved.** The second pass runs over the already-redacted
  text; the opaque deterministic placeholders (`[BSN]` etc.) MUST NOT be
  re-detected, altered, or split by GLiNER/Presidio.
- **Counts merge disjointly** — deterministic types from the first pass, entity
  types (names, etc.) from the second; no type is summed across both.

## Invariants

- **Local only** — GLiNER/Presidio on CPU (GPU via an explicit, revocable
  endpoint only if measured throughput blocks the run; never silently in the
  critical path).
- **Hard failure** — if OpenAnonymiser errors, raise; never emit un-redacted text.
- **Irreversible** — placeholders carry no mapping (pseudonymization is separate).
- **License-compatible** — OpenAnonymiser is EUPL-1.2, but the GLiNER model
  weights (`gliner_multi_pii-v1`) carry their own licence; it MUST be verified
  compatible before the model ships (the EUPL/license invariant covers model
  dependencies, not just code).

## Blocked-on note

OpenAnonymiser is not reachable from this build agent (org hook; not on PyPI).
This spec is ready; the build waits until Mark makes the dependency reachable
(vendor into the repo, publish under a reachable name, or grant access).
