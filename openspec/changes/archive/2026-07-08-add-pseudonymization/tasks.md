# Tasks — add-pseudonymization

Done = green: every task ships with its tests in the same builder run.

## 1. Crypto + keys
- [x] 1.1 Add `cryptography` dependency
- [x] 1.2 `crypto.py`: AES-GCM encrypt/decrypt helpers (nonce per record)
- [x] 1.3 `keys.py`: `KeyProvider` protocol + `StubKeyProvider` (key from passphrase)
- [x] 1.4 Tests: encrypt/decrypt round-trip, wrong key fails; stub key deterministic

## 2. Mapping store (separated)
- [x] 2.1 `pii_mappings` table (pseudonym PK, ciphertext, nonce, key_id, created_at)
- [x] 2.2 `mapping_store.py`: `MappingStore` protocol + `PostgresMappingStore`;
      idempotent `put`, `get`
- [x] 2.3 Tests: put/get round-trip, idempotent put, only ciphertext stored

## 3. Detector reuse
- [x] 3.1 Refactor `detectors.py` to expose a detector registry + generic
      substitution; keep `redact_*` behaviour unchanged (a11y for anonymizer)
- [x] 3.2 Tests: existing detector tests still pass

## 4. Pseudonymizer
- [x] 4.1 `pseudonymizer.py`: `Pseudonymizer` (stable keyed pseudonym per value,
      stores encrypted mapping); satisfies the `Anonymizer` protocol
- [x] 4.2 `deanonymize()`: recover originals from store+key; append a
      `deanonymize` audit record (pseudonyms + actor, no clear values)
- [x] 4.3 Tests: stable pseudonyms; round-trip pseudonymize->deanonymize;
      deanonymize logged and chain still verifies; injectable into `process()`

## 5. Decision
- [x] 5.1 design.md records the separated-store decision (done in propose)
