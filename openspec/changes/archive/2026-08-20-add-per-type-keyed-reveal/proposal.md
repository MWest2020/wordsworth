## Why

Fase B's goal is key-gated **selective** reveal: an operator can reveal some PII
types (e.g. PERSON) while others (e.g. BSN) stay pseudonymised, and the ability to
reveal a type is gated by possession of that type's key — the lever the caller
shares or revokes. Today the reversible `Pseudonymizer` encrypts every type's
mappings under one global key and `deanonymize()` reveals every recognised token
indiscriminately, so there is no per-type gate to grant or withhold.

## What Changes

- **Per-PII-type keys.** `KeyProvider` gains an optional `scope` (the PII type) on
  `current_key`/`rotate`, defaulting to a single global scope for backward
  compatibility. Each type's pseudonyms and mappings are encrypted under that
  type's active key, so a type's key decrypts only that type. `key(key_id)` still
  resolves any version across scopes (deanonymisation is unchanged in shape).
- **Selective reveal.** `deanonymize()` gains `allowed_types`: only tokens whose
  type is allowed *and* whose key the caller can resolve are revealed; the rest
  stay pseudonymised. Two independent gates — the explicit type filter and
  cryptographic key availability. `allowed_types=None` preserves reveal-all.
- **Reveal audit records the types.** The `deanonymize` audit payload additionally
  records which types were requested/revealed (still never any clear value).
- **`InMemoryMappingStore`** added beside `PostgresMappingStore` (dict-backed test
  double + non-DB wiring), mirroring `InMemoryIndex`.

## Capabilities

### Modified Capabilities
- `pseudonymization`: pseudonyms/mappings are per-type keyed; reveal is selective
  by type and gated by per-type key availability; reveal audit records the types.
- `key-lifecycle`: keys are scoped per PII type; rotation is per scope; resolution
  by `key_id` is unchanged.

## Impact

- Code: `keys.py` (scope-aware providers), `pseudonymizer.py` (per-type keying +
  selective `deanonymize` + a pure `_reveal` helper), `mapping_store.py`
  (`InMemoryMappingStore`). No schema change (the type is carried in the token
  prefix already); no pipeline default change (reversible mode stays opt-in).
- Tests: pure/local (per-type keys; pseudonymise + selective reveal via in-memory
  stores, no DB) + DB-integration (selective `deanonymize` + audit) run in CI.
- Foundational for the reveal API, GLiNER-entity coverage, and shareable/revocable
  grants that follow.
