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
- **Document id before the write** (amended after architect FAIL on #305):
  `pipeline.ingest` assigns the document id (or derives it from the content
  hash) BEFORE the store write. `put_original(document_id, key, data)` seals
  under a fresh DEK only for a new document. When `register_live` returns an
  existing document for identical bytes, ingest does not re-seal and does not
  overwrite: it reuses the existing ciphertext and wrapped key. A re-ingest
  therefore leaves one wrapped key and the original ciphertext intact.
- **One live document per object key** (replaces the earlier "shared DEK"
  idea): `uq_documents_live_object_key` allows one live document per object
  key, so there is no shared-key case. Each DEK belongs to exactly one live
  document, and the shred path (`originals-crypto-shred`) may assume that.
- **Unwrap cache is bounded**: `DocumentKeys` keeps unwrapped DEKs in an LRU
  cache with a fixed maximum size; it never grows toward the size of the
  corpus. `DurableKeyProvider._cache` (pseudonymisation keys) is left alone: it
  is keyed per domain, not per document, so it is already bounded by the number
  of domains, and changing it is outside this change.
- **Availability** (decided as a default, pending Mark): ingest fails closed
  with a clear, named error when OpenBao is unreachable. There is no plaintext
  fallback. Irreversible-mode ingest, which needed no key service before, now
  needs it; the how-to and the deploy notes say so.
- **Further guess-points**: the builder resolves any other guess-point in the
  full architect verdict on wordsworth#305 and records each decision here,
  one line per decision, before applying.
