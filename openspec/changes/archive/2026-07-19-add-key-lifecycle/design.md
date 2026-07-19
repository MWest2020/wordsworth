# Design decisions — add-key-lifecycle

## Versioned keys, selection by stored key_id

`KeyProvider` holds multiple key versions; `current_key()` returns the active one,
`key(key_id)` resolves any version. Mappings already store `key_id`, so
deanonymization decrypts each entry with the key it was encrypted under — old and
new coexist during/after rotation.

## Rotation = re-encrypt mappings, never touch documents

`rotate()` creates a new active key. `MappingStore.reencrypt(old_id, new_id)`
walks entries under `old_id`, decrypts with the old key, re-encrypts with the new,
updates `key_id`. Documents and the index are untouched — this is exactly the win
that justified the separated store over in-document XMP.

## Escrow / recovery via open tooling

Keys are stored and escrowed via **SOPS+age** or **OpenBao** — open, auditable,
non-commercial. **CyberArk/Conjur are banned.** Recovery = restore the key
material from escrow; because mappings carry `key_id`, restored keys decrypt their
entries.

## Boundaries

Every deanonymization is already audit-logged (from change b). Rotation itself
SHOULD emit an audit record (rotation event). No key material is ever logged.

## Not in scope

HSM integration, automatic rotation schedules, per-tenant keys — future.
