# Tasks — add-key-lifecycle

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. Versioned keys + rotation
- [ ] 1.1 `KeyProvider`: versioned keys, `current_key`, `key(key_id)`, `rotate`
- [ ] 1.2 Tests: rotate adds active key; prior versions still resolvable

## 2. Key selection on deanonymize
- [ ] 2.1 Deanonymize decrypts each mapping by its stored `key_id`
- [ ] 2.2 Tests: mixed pre/post-rotation mappings all decrypt

## 3. Mapping re-encryption
- [ ] 3.1 `MappingStore.reencrypt(old_id, new_id)`; documents untouched
- [ ] 3.2 Tests: entries decrypt under new key; no document mutated

## 4. Escrow / recovery
- [ ] 4.1 Escrow keys via SOPS+age or OpenBao (no CyberArk/Conjur); recovery path
- [ ] 4.2 Emit a rotation audit record (no key material logged)
- [ ] 4.3 Tests: recovered key decrypts its mappings
