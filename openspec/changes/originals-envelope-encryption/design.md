# Design

- **Format**: `WWENC` magic, 1-byte version, 16-byte DEK `key_id`, 12-byte
  nonce, then the GCM ciphertext + tag. AAD: `document_id || sha256(plaintext)`.
- **Seam**: `EncryptingObjectStore(inner: ObjectStore, keys: DocumentKeys)`
  wraps the S3 driver; callers keep calling `get`/`put`. The document id is
  needed for AAD: `put_original(document_id, key, data)` / `get_original(
  document_id, key)`; plain `get`/`put` stay for non-original objects (redacted
  cache, exports) and are unchanged.
- **Keys**: `DocumentKeys` mints a random 32-byte DEK, wraps it via the
  existing `Transit` seam (FakeTransit in tests), stores the wrapped blob, and
  unwraps with the ADR-0002 unwrap cache. Clear DEK material is never logged,
  never written, never part of an exception message.
- **Dedup**: the same plaintext ingested twice keeps one object; its DEK is the
  first document's, shared by the duplicate (the duplicate's `document_keys`
  row references the same `key_id`). Deletion (later change) only shreds a key
  no live document still references.
