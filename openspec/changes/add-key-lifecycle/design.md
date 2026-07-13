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

## Rotation audit goes to a separate stream, not the document chain

Every deanonymization is already audit-logged (from change b) against its
`document_id`. Rotation is different: it is system-wide and has no document. The
document audit table *is* the document state machine and its `document_id` is
mandatory (NOT NULL FK) — bolting a document-less rotation event onto it would
force either a synthetic document or a nullable `document_id`, both of which
break that invariant. So rotation emits to a **separate append-only
key-lifecycle audit stream** (the reused `zeef` audit-JSONL pattern fits),
recording old/new `key_id` + actor. No key material is ever logged.

## Re-encryption reads by key_id and updates in place

`MappingStore` today exposes only `put`/`get(pseudonym)`; `reencrypt` needs a
list-by-`key_id` read to walk the entries under `old_id`, so the store's read
surface is extended. Re-encryption updates each row in place — it does NOT route
through `put`, which is idempotent and skips existing pseudonyms.

## Not in scope

HSM integration, automatic rotation schedules, per-tenant keys — future.
