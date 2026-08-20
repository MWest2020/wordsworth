## 1. Detection seam + default engine

- [x] 1.1 `Entity` (type + span) and a `DetectFn = (text) -> list[Entity]` seam.
- [x] 1.2 Default `detect_entities` calls OpenAnonymiser, reuses chunking/concurrency,
  maps per-chunk spans back to whole-text offsets.

## 2. Reversible entity driver

- [x] 2.1 `ReversibleAnonymizer` runs deterministic keyed pass (reusing
  `Pseudonymizer`) then entity pass; merges counts.
- [x] 2.2 Entity spans → `[TYPE:hash]` keyed tokens under the type's per-type key,
  encrypted mapping stored; right-to-left, non-overlapping, slice-verified.
- [x] 2.3 Fail-hard: detection error → `AnonymizationEngineError`, no leak.

## 3. Gate

- [x] 3.1 Local tests (fake detector): compose det+entity, per-type key, selective
  reveal PERSON-not-BSN, reveal-all, stable pseudonym, fail-hard no-leak, overlap.
- [x] 3.2 DB-integration test (CI): entity deanonymize with allowed_types, chain
  verifies, audit records types with no clear values.
- [x] 3.3 Full suite green in CI + `openspec validate`.
