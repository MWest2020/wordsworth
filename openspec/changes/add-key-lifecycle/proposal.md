## Why

Pseudonymization ships with a stub `KeyProvider`: one dev key, no rotation,
escrow, or recovery. The 10-year auditability requirement (gap 1) needs a real key
lifecycle — and the separated mapping store makes it cheap: rotate the key and
re-encrypt the mappings without touching a single document.

## What Changes

- Extend the **`KeyProvider`** to versioned keys (`key_id`) with **rotation**, and
  **escrow/recovery** via open tooling (SOPS+age or OpenBao) — never commercial
  (CyberArk/Conjur banned).
- Add **mapping re-encryption** on rotation: `MappingStore` re-encrypts each
  entry from the old key to the new, updating `key_id`; documents are untouched.
- Deanonymization SHALL select the decryption key by the mapping's stored
  `key_id` (already persisted), so old and rotated mappings both decrypt.
- Rotation SHALL be audited in a **separate key-lifecycle stream** (not the
  document hash-chain, whose records require a `document_id`).

## Capabilities

### New Capabilities
- `key-lifecycle`: versioned keys, rotation, escrow/recovery, and mapping
  re-encryption.

## Impact

- Integrates SOPS+age or OpenBao for key storage/escrow. Reuses `key_id` already
  on `pii_mappings`. No document changes on rotation (separated-store payoff).
  Does not touch `CLAUDE.md`, `.claude/agents/`, CI.
