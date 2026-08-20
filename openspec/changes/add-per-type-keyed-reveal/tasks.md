## 1. Per-type keys

- [x] 1.1 `KeyProvider.current_key(scope=...)` / `rotate(scope=...)`, default global
  scope; `key(key_id)` resolves any version across scopes.
- [x] 1.2 `InMemoryKeyProvider` holds keys per scope; distinct scopes → distinct
  active keys; `StubKeyProvider` stays single-key (scope ignored).

## 2. Selective reveal

- [x] 2.1 Pure `_reveal(text, allowed_types, get_mapping, get_key)` helper: type
  filter + key-availability gate, returns (restored, revealed-tokens).
- [x] 2.2 `Pseudonymizer.anonymize` encrypts each type under its type-scoped key.
- [x] 2.3 `deanonymize(..., allowed_types=None)` uses `_reveal`; audit payload adds
  the revealed types; `allowed_types=None` keeps reveal-all.
- [x] 2.4 `InMemoryMappingStore` added (satisfies `MappingStore`).

## 3. Gate

- [x] 3.1 Local tests (no DB): per-type keys distinct + resolvable; pseudonymise
  then selective reveal (allow EMAIL not BSN); key-availability gate leaves a type
  pseudonymised when its key is absent.
- [ ] 3.2 DB-integration test (CI): selective `deanonymize` reveals only allowed
  types, chain still verifies, payload records types and no clear values.
- [ ] 3.3 Full suite green in CI + `openspec validate`.
