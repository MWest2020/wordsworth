# Tasks — add-key-lifecycle

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. Versioned keys + rotation
- [x] 1.1 `KeyProvider`: versioned keys, `current_key`, `key(key_id)`, `rotate`
- [x] 1.2 Tests: rotate adds active key; prior versions still resolvable

## 2. Key selection on deanonymize
- [x] 2.1 Deanonymize decrypts each mapping by its stored `key_id`
- [x] 2.2 Tests: mixed pre/post-rotation mappings all decrypt

## 3. Mapping re-encryption
- [ ] 3.1 Extend `MappingStore` read surface with a list-by-`key_id` query
  (`get`/`put` alone cannot walk entries under `old_id`)
- [ ] 3.2 `MappingStore.reencrypt(old_id, new_id)`; updates rows in place (NOT via
  idempotent `put`, which skips existing pseudonyms); documents untouched
- [ ] 3.3 Tests: entries decrypt under new key; no document mutated

## 4. Escrow / recovery
- [ ] 4.1 Escrow keys via SOPS+age or OpenBao (no CyberArk/Conjur); recovery path
- [ ] 4.2 Emit a rotation event to a SEPARATE key-lifecycle audit stream (old/new
  `key_id` + actor; no key material) — NOT the document hash-chain
- [ ] 4.3 Tests: recovered key decrypts its mappings; rotation event recorded in
  the key-lifecycle stream and the document chain is unchanged
