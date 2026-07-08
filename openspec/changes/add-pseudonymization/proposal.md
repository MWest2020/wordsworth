## Why

Anonymization is irreversible. Pseudonymization keeps reducibility under control:
the search index still never sees clear PII, but the original values can be
recovered by an authorised party with the key. This is wordsworth's
distinguishing capability over generic RAG stacks. The 10-year auditability
requirement is a product concern, not a PoC one — so here we establish the
architecture (protocols, a separated encrypted store, audit-logged
deanonymization) with stubs behind it, without anything that slows searchability.

## What Changes

- Introduce a **`KeyProvider` protocol** with a dev **stub** (key derived from a
  user-supplied passphrase). Full lifecycle (rotation, escrow, recovery) is
  explicitly out of scope for the PoC.
- Introduce a **`MappingStore` protocol** with a PostgreSQL implementation: a
  **separated** encrypted store (pseudonym → AES-GCM ciphertext), not in-document.
- Add a **`Pseudonymizer`** that reuses the deterministic detectors, replaces
  each PII value with a **stable keyed pseudonym**, and stores the encrypted
  original in the MappingStore. It satisfies the existing `Anonymizer` protocol,
  so it is injectable into the pipeline's de-identify step as an alternative
  driver — the search index sees pseudonyms, never clear PII.
- Add **`deanonymize`**: recover originals from the store + key, and **log every
  deanonymization** as a record in the append-only, hash-chained audit trail
  (logging the pseudonyms and actor — never the recovered clear values).

## Capabilities

### New Capabilities
- `pseudonymization`: the `KeyProvider`/`MappingStore` protocols and stubs, the
  `Pseudonymizer`, the separated-store decision, and audit-logged deanonymization.

### Modified Capabilities
<!-- none: pseudonymization is a new capability and an alternative de-identify
     driver; the pipeline default (irreversible anonymization) is unchanged. -->

## Impact

- New dependency: `cryptography` (AES-GCM; Apache-2.0/BSD, license-clean).
- New module surface: `crypto`, `keys`, `mapping_store`, `pseudonymizer`; new
  `pii_mappings` table (separated store, holds only ciphertext — never clear PII).
- `detectors` refactored to expose a detector registry reused by both the
  anonymizer and the pseudonymizer (behaviour unchanged).
- No cloud, no key lifecycle beyond the stub. Does not touch `CLAUDE.md`,
  `.claude/agents/`, or CI.
